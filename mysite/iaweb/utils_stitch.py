# ─── desactivar OpenCL ANTES de cargar cv2 ───────────────────────
import os
os.environ["OPENCV_OPENCL_RUNTIME"] = "disabled"   # fuerza CPU

import cv2
cv2.ocl.setUseOpenCL(False)                        # doble seguridad
# ────────────────────────────────────────────────────────────────

import numpy as np
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image
from tqdm import tqdm
import time

WHITE_PIX_THRESHOLD = 0.60
DOWNSCALE_FACTOR    = 0.25        # 25 % (menos RAM / key-points)


# ────────────────────────────────────────────────────────────────
#  Filtros
# ────────────────────────────────────────────────────────────────
def is_mostly_white(cv_img, ratio=WHITE_PIX_THRESHOLD):
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    white = np.sum(gray > 240)
    return white / gray.size >= ratio


def build_useful_images(sample):
    imgs = list(sample.images.filter(is_mosaic=False).order_by("id"))
    useful = []
    t0 = time.time()

    for simg in tqdm(imgs, desc="Filtrando imágenes", unit="img"):
        cv_img = cv2.imread(simg.image.path)
        small  = cv2.resize(cv_img, None, fx=DOWNSCALE_FACTOR, fy=DOWNSCALE_FACTOR)
        if is_mostly_white(small):
            continue
        useful.append(simg)

    print(f"Filtro blancos: {len(useful)}/{len(imgs)} válidas "
          f"en {time.time() - t0:.1f}s")
    return useful


# ────────────────────────────────────────────────────────────────
#  Crop opcional
# ────────────────────────────────────────────────────────────────
def smart_crop(cv_img):
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    _, th  = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return cv_img
    x, y, w, h = cv2.boundingRect(max(cnts, key=cv2.contourArea))
    return cv_img[y:y+h, x:x+w]


# ────────────────────────────────────────────────────────────────
#  OpenCV stitching con fallback
# ────────────────────────────────────────────────────────────────
def _try_stitch(cv_imgs, mode):
    stitcher = cv2.Stitcher_create(mode)
    status, pano = stitcher.stitch(cv_imgs)
    return status, pano


def _opencv_stitch(cv_imgs):
    status, pano = _try_stitch(cv_imgs, cv2.Stitcher_PANORAMA)
    if status == cv2.Stitcher_OK:
        return pano
    print(f"PANORAMA falló ({status}), probando SCANS…")

    status, pano = _try_stitch(cv_imgs, cv2.Stitcher_SCANS)
    if status == cv2.Stitcher_OK:
        return pano
    raise RuntimeError(f"Stitching failed (PANORAMA={status}, SCANS={status})")


# ────────────────────────────────────────────────────────────────
#  Modos públicos
# ────────────────────────────────────────────────────────────────
def _resize_list(imgs, scale=DOWNSCALE_FACTOR):
    return [cv2.resize(img, None, fx=scale, fy=scale) for img in imgs]


def stitch_circular(sample):
    sims = build_useful_images(sample)
    if not sims:
        raise RuntimeError("No images after filtering")

    t0 = time.time()
    cv_imgs = _resize_list([cv2.imread(s.image.path) for s in sims])
    print("→ OpenCV stitching (circular)…")
    pano = _opencv_stitch(cv_imgs)
    print(f"Stitch circular listo en {time.time() - t0:.1f}s")
    return pano


def stitch_cropped(sample):
    sims = build_useful_images(sample)
    if not sims:
        raise RuntimeError("No images after filtering")

    t0 = time.time()
    raw = [smart_crop(cv2.imread(s.image.path)) for s in sims]
    h0, w0 = raw[0].shape[:2]
    cv_imgs = [cv2.resize(img, (w0, h0)) for img in raw]
    cv_imgs = _resize_list(cv_imgs)                 # bajar a 25 %
    print("→ OpenCV stitching (cropped)…")
    pano = _opencv_stitch(cv_imgs)
    print(f"Stitch cropped listo en {time.time() - t0:.1f}s")
    return pano


# ────────────────────────────────────────────────────────────────
#  Guardar mosaico
# ────────────────────────────────────────────────────────────────
def save_mosaic(sample, cv_img, suffix):
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    buf = BytesIO()
    pil.save(buf, format="JPEG", quality=95)
    filename = f"{sample.id}_{suffix}.jpg"
    return sample.images.create(
        is_mosaic=True,
        image=ContentFile(buf.getvalue(), name=filename)
    )
