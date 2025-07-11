# ───────────────────────── utils_stitch.py ───────────────────────────
"""
Construye un mosaico de mini-fotos (tipo *contact-sheet*) en cuadrícula.

 • Cada sub-imagen:
       – se recorta al mayor cuadrado inscrito en el ocular
       – **no lleva marco negro permanente**
 • Filtros rápidos:
       – descarta fotos casi negras, casi blancas o con pocos puntos SIFT
       – evita duplicados con hash perceptual (pHash)
 • Antes de montar el mosaico TODAS las teselas se igualan al mismo
   tamaño ⇒ ya no aparecen líneas negras por desajustes de 1-2 px.
 • Se guarda un JPEG final y (opcional) un PNG de depuración con la
   rejilla dibujada.

"""

import os, cv2, numpy as np, time, math, random
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from tqdm import tqdm

# ───── Intenta usar imagehash para detectar duplicados ───────────────
try:
    import imagehash
    _USE_HASH = True
except ModuleNotFoundError:
    imagehash = None
    _USE_HASH = False

# ───── Desactivar OpenCL (-220 en Windows) ───────────────────────────
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
cv2.ocl.setUseOpenCL(False)

# 1. Parámetros globales (ajusta a tu gusto) ──────────────────────────
DOWNSCALE_FACTOR = 0.25     # escala de las miniaturas para los filtros (0-1)
BLACK_RATIO      = 0.65     # ≥ 65 % negro  → descartar
WHITE_RATIO      = 0.10     # ≥ 30 % blanco → descartar
MIN_KEYPOINTS    = 60       # < 60 puntos SIFT → descartar
MAX_FRAMES       = 49       # límite superior de teselas
BORDER_PX        = 0        # borde permanente (0 = sin borde)
BORDER_THUMB     = 1        # borde solo en el PNG de depuración
THUMB_GRID_SIDE  = 150      # tamaño de cada miniatura en el PNG
DEBUG_MOSAIC     = True     # guarda el PNG de depuración
HASH_DIST_MAX    = 1        # distancia de Hamming máx. para duplicados

_sift = cv2.SIFT_create()

# ───── helpers de recorte ────────────────────────────────────────────
def _crop_circle_to_square(img):
    """Recorta el mayor cuadrado inscrito en la foto del ocular."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:                         # si está vacía
        return img

    (x, y), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    half = int(r / math.sqrt(2))         # mitad del cuadrado inscrito
    cx, cy = int(x), int(y)
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    sq = img[max(0, y0):min(img.shape[0], y1),
             max(0, x0):min(img.shape[1], x1)].copy()

    # solo si quisieras volver a poner borde permanente
    if BORDER_PX:
        sq = cv2.copyMakeBorder(
            sq, BORDER_PX, BORDER_PX, BORDER_PX, BORDER_PX,
            cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )
    return sq

# ───── filtros rápidos ───────────────────────────────────────────────
def _mostly_black(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (gray < 30).mean() >= BLACK_RATIO

def _mostly_white(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (gray > 225).mean() >= WHITE_RATIO

def _too_few_features(img):
    kp = _sift.detect(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None)
    return len(kp) < MIN_KEYPOINTS

def _is_duplicate(phash, seen):
    if not _USE_HASH:
        return False
    return any(phash - h <= HASH_DIST_MAX for h in seen)

# ───── cuadrícula-debug (“contact sheet”) ────────────────────────────
def _save_thumbgrid(imgs, sample, suffix="thumbs"):
    if not (DEBUG_MOSAIC and imgs):
        return
    cols = int(math.sqrt(len(imgs)))
    rows = math.ceil(len(imgs) / cols)
    cell = THUMB_GRID_SIDE
    grid = np.zeros((rows * cell, cols * cell, 3), np.uint8)

    for idx, img in enumerate(imgs):
        r, c = divmod(idx, cols)
        thumb = cv2.resize(img, (cell, cell))
        if BORDER_THUMB:
            cv2.rectangle(thumb, (0, 0), (cell - 1, cell - 1),
                          (0, 0, 0), BORDER_THUMB)
        grid[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = thumb

    rgb = cv2.cvtColor(grid, cv2.COLOR_BGR2RGB)
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    sample.images.create(
        is_mosaic=True,
        image=ContentFile(buf.getvalue(), name=f"{sample.id}_{suffix}.png")
    )

# ───── normalización de tamaño ───────────────────────────────────────
def _standardize_tiles(imgs):
    """Recorta todas las teselas al mismo (mínimo) tamaño para
    que casen sin dejar huecos negros."""
    if not imgs:
        return imgs
    h_min = min(im.shape[0] for im in imgs)
    w_min = min(im.shape[1] for im in imgs)
    std = []
    for im in imgs:
        h, w = im.shape[:2]
        y0 = (h - h_min) // 2
        x0 = (w - w_min) // 2
        std.append(im[y0:y0 + h_min, x0:x0 + w_min])
    return std

# ───── obtención + filtrado de frames ────────────────────────────────
def _gather(sample):
    raw = list(sample.images.filter(is_mosaic=False).order_by("id"))
    useful, thumbs, hashes = [], [], set()
    t0 = time.time()

    for simg in tqdm(raw, desc="Filtrando imágenes", unit="img"):
        img = cv2.imread(simg.image.path)
        img = _crop_circle_to_square(img)
        mini = cv2.resize(img, None,
                          fx=DOWNSCALE_FACTOR, fy=DOWNSCALE_FACTOR)

        # filtros rápidos
        if _mostly_black(mini) or _mostly_white(mini) or _too_few_features(mini):
            continue

        if _USE_HASH:
            phash = imagehash.phash(Image.fromarray(
                cv2.cvtColor(mini, cv2.COLOR_BGR2RGB)))
            if _is_duplicate(phash, hashes):
                continue
            hashes.add(phash)

        useful.append(img)      # resolución completa
        thumbs.append(mini)     # miniatura para depuración

    # límite de teselas
    if MAX_FRAMES and len(useful) > MAX_FRAMES:
        keep = random.sample(range(len(useful)), MAX_FRAMES)
        useful = [useful[i] for i in keep]
        thumbs = [thumbs[i] for i in keep]

    # ——— NUEVO: igualar tamaños antes de devolver ———
    useful = _standardize_tiles(useful)

    print(f"Quedan {len(useful)}/{len(raw)} útiles ({time.time() - t0:.1f}s)")
    _save_thumbgrid(thumbs, sample)
    return useful

# ───── montaje en cuadrícula ─────────────────────────────────────────
def _grid_mosaic(imgs):
    if not imgs:
        raise RuntimeError("No hay teselas que montar")

    h, w = imgs[0].shape[:2]
    cols = math.ceil(math.sqrt(len(imgs)))
    rows = math.ceil(len(imgs) / cols)

    canvas = np.zeros((rows * h, cols * w, 3), dtype=np.uint8)
    for idx, im in enumerate(imgs):
        r, c = divmod(idx, cols)
        y0, x0 = r * h, c * w
        canvas[y0:y0 + h, x0:x0 + w] = im
    return canvas

# ───── API pública ──────────────────────────────────────────────────
def stitch_cropped(sample):
    imgs = _gather(sample)
    if not imgs:
        raise RuntimeError("No hay imágenes válidas")

    print("→ Construyendo mosaico cuadrícula…")
    return _grid_mosaic(imgs)

# compatibilidad
stitch_circular = stitch_cropped

# ───── guardar JPEG (≈ 1-2 MB, calidad 95 %) ─────────────────────────
def save_mosaic(sample, cv_img, suffix):
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=95)
    return sample.images.create(
        is_mosaic=True,
        image=ContentFile(buf.getvalue(),
                          name=f"{sample.id}_{suffix}.jpg")
    )
# ─────────────────────────────────────────────────────────────────────
