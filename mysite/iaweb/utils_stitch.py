# ───────────────────────── utils_stitch.py ───────────────────────────
"""
Construye un mosaico de mini-fotos (tipo contact-sheet) en cuadrícula.

 • Cada sub-imagen:
        – se recorta al mayor cuadrado inscrito en el ocular
        – recibe un marco negro para que la unión sea visible
 • Filtros rápidos:
        – descarta fotos casi negras, casi blancas o con pocos puntos SIFT
        – evita duplicados con hash perceptual (pHash)
 • Se ensamblan como matriz (sin solaparse) y se guarda el JPEG final
   + PNG opcional con la cuadrícula de miniaturas para depuración
"""

import os, cv2, numpy as np, time, math, random, itertools
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
WHITE_RATIO      = 0.65     # ≥ 65 % blanco → descartar
MIN_KEYPOINTS    = 60       # < 60 puntos SIFT → descartar
MAX_FRAMES       = 100      # **límite de teselas en el mosaico**
BORDER_PX        = 8        # grosor del marco negro de cada tesela
THUMB_GRID_SIDE  = 150      # px de cada miniatura en el grid‐debug
DEBUG_MOSAIC     = True     # guarda PNG con la cuadrícula de miniaturas
HASH_DIST_MAX    = 8        # distancia Hamming máx. para considerar duplicado

_sift = cv2.SIFT_create()

# ───── helpers de recorte ────────────────────────────────────────────
def _crop_circle_to_square(img):
    """
    Recorta el mayor cuadrado inscrito en la foto del ocular y añade
    un marco negro. Devuelve SIEMPRE un cuadrado con borde.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:                         # si está vacía, devolver tal cual
        return img

    (x, y), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    s  = int(r / math.sqrt(2))           # mitad del cuadrado inscrito
    cx, cy = int(x), int(y)
    x0, y0, x1, y1 = cx - s, cy - s, cx + s, cy + s
    sq = img[max(0, y0):min(img.shape[0], y1),
             max(0, x0):min(img.shape[1], x1)].copy()

    return cv2.copyMakeBorder(
        sq, BORDER_PX, BORDER_PX, BORDER_PX, BORDER_PX,
        cv2.BORDER_CONSTANT, value=(0, 0, 0)
    )

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
    # cualquiera a distancia de Hamming ≤ HASH_DIST_MAX se considera duplicado
    return any(phash - h <= HASH_DIST_MAX for h in seen)

# ───── cuadrícula-debug (“contact sheet”) ────────────────────────────
def _save_thumbgrid(imgs, sample, suffix="thumbs"):
    if not imgs:
        return
    cols = int(math.sqrt(len(imgs)))
    rows = math.ceil(len(imgs) / cols)
    cell = THUMB_GRID_SIDE
    grid = np.zeros((rows * cell, cols * cell, 3), np.uint8)

    for idx, img in enumerate(imgs):
        r, c = divmod(idx, cols)
        thumb = cv2.resize(img, (cell, cell))
        grid[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = thumb

    rgb = cv2.cvtColor(grid, cv2.COLOR_BGR2RGB)
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, "PNG")
    sample.images.create(
        is_mosaic=True,
        image=ContentFile(buf.getvalue(), name=f"{sample.id}_{suffix}.png")
    )

# ───── obtención + filtrado de frames ────────────────────────────────
def _gather(sample):
    """
    Lee, recorta y filtra todas las sub-fotos del `sample`.
    Devuelve la lista de teselas válidas (resolución completa).
    """
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

        # duplicados (solo si imagehash está disponible)
        if _USE_HASH:
            phash = imagehash.phash(Image.fromarray(cv2.cvtColor(mini, cv2.COLOR_BGR2RGB)))
            if _is_duplicate(phash, hashes):
                continue
            hashes.add(phash)

        useful.append(img)      # resolución completa
        thumbs.append(mini)     # miniatura para depuración

    # límite superior de teselas
    if MAX_FRAMES and len(useful) > MAX_FRAMES:
        keep_idx = random.sample(range(len(useful)), MAX_FRAMES)
        useful  = [useful[i]  for i in keep_idx]
        thumbs  = [thumbs[i]  for i in keep_idx]

    print(f"Quedan {len(useful)}/{len(raw)} útiles ({time.time() - t0:.1f}s)")
    if DEBUG_MOSAIC:
        _save_thumbgrid(thumbs, sample)
    return useful

# ───── montaje en cuadrícula ─────────────────────────────────────────
def _grid_mosaic(imgs):
    """
    Ensambla las teselas en una matriz:
        columnas = ⌈√N⌉  → forma lo más cuadrada posible
    """
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

# ───── API pública que usa admin.py ──────────────────────────────────
def stitch_cropped(sample):
    """
    Construye la cuadrícula (cropped+border) con todas las sub-fotos
    válidas de `sample` y la devuelve como BGR (lista para `save_mosaic`).
    """
    imgs = _gather(sample)
    if not imgs:
        raise RuntimeError("No hay imágenes válidas")

    print("→ Construyendo mosaico cuadrícula…")
    pano = _grid_mosaic(imgs)
    return pano

# El modo circular ahora llama al mismo proceso (para compatibilidad)
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
