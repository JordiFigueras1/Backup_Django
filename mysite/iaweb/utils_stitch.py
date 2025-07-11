# ───────────────────────── utils_stitch.py ───────────────────────────
"""
Construye un mosaico de mini-fotos como cuadrícula.
 ▸  Cada sub-imagen se recorta al mayor cuadrado inscrito
 ▸  Se le añade un borde negro para que las uniones queden visibles
 ▸  Se colocan en una matriz (≈ contact-sheet) sin solaparse
"""

import os, cv2, numpy as np, time, math, random
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from tqdm import tqdm

# 0. Desactivar OpenCL – evita cuelgues en Windows
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
cv2.ocl.setUseOpenCL(False)

# 1. Parámetros globales (ajusta a tu gusto) ──────────────────────────
DOWNSCALE_FACTOR = .25      # miniaturas para el thumb-grid            (0-1)
BLACK_RATIO      = .65      # ≥ 65 % negro  ⇒  se descarta la foto
MIN_KEYPOINTS    = 60       # < 60 puntos SIFT ⇒  se descarta la foto
MAX_FRAMES       = None     # p.e. 60  ⇒ límite superior de teselas
BORDER_PX        = 8        # grosor del marco negro alrededor de CADA tesela
THUMB_GRID_SIDE  = 150      # tamaño (px) de las miniaturas del grid-debug
DEBUG_MOSAIC     = True     # guarda PNG con la cuadrícula de miniaturas

_sift = cv2.SIFT_create()

# ───── helpers de recorte ────────────────────────────────────────────
def _crop_circle_to_square(img):
    """
    Recorta el mayor cuadrado inscrito en una foto circular y añade un borde
    negro uniforme.  El resultado es siempre cuadrado + marco.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, m = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:         # lienzo en blanco → se devuelve tal cual
        return img

    (x, y), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    s  = int(r / math.sqrt(2))                 # mitad del cuadrado inscrito
    cx, cy = int(x), int(y)
    x0, y0, x1, y1 = cx - s, cy - s, cx + s, cy + s
    sq = img[max(0, y0):min(img.shape[0], y1),
             max(0, x0):min(img.shape[1], x1)].copy()

    # marco negro para que la unión sea visible
    return cv2.copyMakeBorder(sq, BORDER_PX, BORDER_PX,
                              BORDER_PX, BORDER_PX,
                              cv2.BORDER_CONSTANT, value=(0, 0, 0))


# ───── filtros rápidos ───────────────────────────────────────────────
def _mostly_black(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (gray < 30).mean() >= BLACK_RATIO

def _too_few_features(img):
    kp = _sift.detect(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None)
    return len(kp) < MIN_KEYPOINTS

# ───── cuadrícula-debug (“contact sheet”) ────────────────────────────
def _save_thumbgrid(imgs, sample, suffix="thumbs"):
    """
    Guarda un PNG con la cuadrícula de miniaturas que finalmente
    entran al mosaico → sirve para comprobar cuántas teselas hay.
    """
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
        image=ContentFile(buf.getvalue(),
                          name=f"{sample.id}_{suffix}.png")
    )

# ───── obtención + filtrado de frames ────────────────────────────────
def _gather(sample):
    """Lee, recorta y filtra todas las sub-fotos del `sample`."""
    raw = list(sample.images.filter(is_mosaic=False).order_by("id"))
    useful, thumbs = [], []
    t0 = time.time()

    for simg in tqdm(raw, desc="Filtrando imágenes", unit="img"):
        img = cv2.imread(simg.image.path)
        img = _crop_circle_to_square(img)

        mini = cv2.resize(img, None,
                          fx=DOWNSCALE_FACTOR, fy=DOWNSCALE_FACTOR)

        if _mostly_black(mini) or _too_few_features(mini):
            continue

        useful.append(img)      # resolución completa
        thumbs.append(mini)     # miniatura (para debug)

    if MAX_FRAMES and len(useful) > MAX_FRAMES:
        keep = random.sample(range(len(useful)), MAX_FRAMES)
        useful = [useful[i] for i in keep]
        thumbs = [thumbs[i] for i in keep]

    print(f"Quedan {len(useful)}/{len(raw)} útiles ({time.time() - t0:.1f}s)")
    _save_thumbgrid(thumbs, sample) if DEBUG_MOSAIC else None
    return useful

# ───── montaje en cuadrícula ─────────────────────────────────────────
def _grid_mosaic(imgs):
    """
    Ensambla las teselas en una matriz sencilla.
    - Se asume que todas miden lo mismo (tras crop + borde)
    - Nº de columnas = ⌈√N⌉   →  forma lo más cuadrada posible
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

# ───── API pública que utiliza admin.py ──────────────────────────────
def stitch_cropped(sample):
    """
    Construye una cuadrícula (cropped+border) con todas las sub-fotos
    de `sample` y la devuelve como BGR (lista para `save_mosaic`).
    """
    imgs = _gather(sample)
    if not imgs:
        raise RuntimeError("No hay imágenes válidas")

    print("→ Construyendo mosaico cuadrícula…")
    pano = _grid_mosaic(imgs)
    return pano


# el modo circular aquí delega al mismo método (puedes quitarlo si no
# lo necesitas, pero lo mantengo por compatibilidad con admin.py)
stitch_circular = stitch_cropped

# ───── guardar JPEG (≈ 1-2 MB con calidad 95 %) ──────────────────────
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
