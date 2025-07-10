# ───── Desactivar OpenCL de OpenCV (evita crash en Windows) ───────────
import os, cv2, numpy as np, time
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from tqdm import tqdm
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"
cv2.ocl.setUseOpenCL(False)
# ──────────────────────────────────────────────────────────────────────

#  --- parámetros “rápidos” ----------------------------------------------------
DOWNSCALE_FACTOR = .30     # 30 % ⇒ ±4 × más rápido al empalmar
BLACK_RATIO      = .65     # ≥65 % negro ⇒ descartar frame
MIN_KEYPOINTS    = 60      # <60 kp SIFT  ⇒ descartar frame
# ------------------------------------------------------------------------------

_sift = cv2.SIFT_create()

# ─────────────────────────////  C R O P  ////─────────────────────────
def _crop_circle_to_square(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return img
    (x, y), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    s = int(int(r) / 1.4142)                 # r / √2
    cx, cy = int(x), int(y)
    x0, y0, x1, y1 = cx - s, cy - s, cx + s, cy + s
    return img[max(0, y0):min(img.shape[0], y1),
               max(0, x0):min(img.shape[1], x1)]

def _crop_freeform(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 30, 255, cv2.THRESH_BINARY)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return img
    x, y, w, h = cv2.boundingRect(max(cnts, key=cv2.contourArea))
    return img[y:y + h, x:x + w]

def _mostly_black(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (gray < 30).mean() >= BLACK_RATIO

def _too_few_features(img):
    kp = _sift.detect(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), None)
    return len(kp) < MIN_KEYPOINTS

# ─────────────────────────////  P R O C E S O  ////───────────────────
def _gather(sample, mode="square"):
    raw = list(sample.images.filter(is_mosaic=False).order_by("id"))
    useful, t0 = [], time.time()
    crop_fn = _crop_circle_to_square if mode == "square" else _crop_freeform

    for simg in tqdm(raw, desc="Filtrando imágenes", unit="img"):
        img = cv2.imread(simg.image.path)
        img = crop_fn(img)

        thumb = cv2.resize(img, None, fx=DOWNSCALE_FACTOR, fy=DOWNSCALE_FACTOR)
        if _mostly_black(thumb) or _too_few_features(thumb):
            continue
        useful.append(img)

    print(f"Quedan {len(useful)}/{len(raw)} útiles ({time.time()-t0:.1f}s)")
    return useful

def _resize(imgs):
    return [cv2.resize(i, None, fx=DOWNSCALE_FACTOR, fy=DOWNSCALE_FACTOR) for i in imgs]

def _opencv_stitch(imgs):
    for mode in (cv2.Stitcher_PANORAMA, cv2.Stitcher_SCANS):
        try:
            stat, pano = cv2.Stitcher_create(mode).stitch(imgs)
            if stat == cv2.Stitcher_OK:
                return pano
        except cv2.error as e:
            # Error típico de FLANN cuando no hay matches suficientes
            print("OpenCV error:", e)
    raise RuntimeError("Stitching OpenCV falló (muy pocos matches entre frames)")

# ─────────────────────────////  A P I   P Ú B L I C A  ////───────────
def stitch_cropped(sample):
    imgs = _gather(sample, "square")
    if not imgs:
        raise RuntimeError("No hay imágenes útiles")
    print("→ Stitching cropped (cuadrado)…")
    return _opencv_stitch(_resize(imgs))

def stitch_circular(sample):
    imgs = _gather(sample, "circle")
    if not imgs:
        raise RuntimeError("No hay imágenes útiles")
    print("→ Stitching circular…")
    return _opencv_stitch(_resize(imgs))

# ─────────────────────────////  G U A R D A R  ////───────────────────
def save_mosaic(sample, cv_img, suffix):
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, "JPEG", quality=95)
    return sample.images.create(
        is_mosaic=True,
        image=ContentFile(buf.getvalue(),
                          name=f"{sample.id}_{suffix}.jpg"))
