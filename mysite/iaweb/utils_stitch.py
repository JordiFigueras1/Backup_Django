import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image

WHITE_PIX_THRESHOLD = 0.60      # 60 % blancos ⇒ descartar
DUP_SSIM_THRESHOLD  = 0.99      # SSIM ≥ 0.99 ⇒ duplicada


# ────────────────────────────────────────────────────────────────
#  Filtros
# ────────────────────────────────────────────────────────────────
def is_mostly_white(cv_img, ratio=WHITE_PIX_THRESHOLD):
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    white = np.sum(gray > 240)           # píxeles muy claros
    return white / gray.size >= ratio


def are_almost_equal(img1, img2, thresh=DUP_SSIM_THRESHOLD):
    gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    h = min(gray1.shape[0], gray2.shape[0])
    w = min(gray1.shape[1], gray2.shape[1])
    gray1, gray2 = gray1[:h, :w], gray2[:h, :w]
    score, _ = ssim(gray1, gray2, full=True)
    return score >= thresh


def build_useful_images(sample):
    """
    Devuelve una lista de objetos SampleImage **válidos**:
      · no son mayoritariamente blancos
      · no son duplicados entre sí
      · is_mosaic=False
    """
    imgs = list(sample.images.filter(is_mosaic=False).order_by("id"))
    useful = []
    for simg in imgs:
        cv_img = cv2.imread(simg.image.path)
        if is_mostly_white(cv_img):
            continue
        if any(are_almost_equal(cv_img, cv2.imread(u.image.path))
               for u in useful):
            continue
        useful.append(simg)
    return useful


# ────────────────────────────────────────────────────────────────
#  Crop opcional (para modo “cuadrado”)
# ────────────────────────────────────────────────────────────────
def smart_crop(cv_img):
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL,
                               cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return cv_img
    x, y, w, h = cv2.boundingRect(max(cnts, key=cv2.contourArea))
    return cv_img[y:y + h, x:x + w]


# ────────────────────────────────────────────────────────────────
#  OpenCV stitching
# ────────────────────────────────────────────────────────────────
def _opencv_stitch(cv_images):
    stitcher = cv2.Stitcher_create()
    status, pano = stitcher.stitch(cv_images)
    if status != cv2.Stitcher_OK:
        raise RuntimeError(f"Stitching failed: {status}")
    return pano


def stitch_circular(sample):
    sims = build_useful_images(sample)
    cv_imgs = [cv2.imread(s.image.path) for s in sims]
    return _opencv_stitch(cv_imgs)


def stitch_cropped(sample):
    sims = build_useful_images(sample)
    cv_imgs = [smart_crop(cv2.imread(s.image.path)) for s in sims]
    return _opencv_stitch(cv_imgs)


# ────────────────────────────────────────────────────────────────
#  Guardar mosaico en BD
# ────────────────────────────────────────────────────────────────
def save_mosaic(sample, cv_img, suffix):
    rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)
    buffer = BytesIO()
    pil.save(buffer, format="JPEG", quality=95)
    filename = f"{sample.id}_{suffix}.jpg"
    return sample.images.create(
        is_mosaic=True,
        image=ContentFile(buffer.getvalue(), name=filename)
    )
