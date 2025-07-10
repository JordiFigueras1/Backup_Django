from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import DiagnosisReport, SampleImage, Sample
# IA DESACTIVADA ────────────────────────────────────────────────
# de momento no importamos ni creamos el detector YOLO
# from .utils import YOLOv5Detector
from django.core.files import File
import os
import shutil
from collections import Counter
from django.utils import timezone
from .utils import calculate_parasite_density

# IA DESACTIVADA ────────────────────────────────────────────────
# yolo_detector = YOLOv5Detector()


# -----------------------------------------------------------------
# 1. Al llegar una nueva imagen: NO ejecutamos IA ni recortamos
# -----------------------------------------------------------------
@receiver(post_save, sender=SampleImage)
def run_yolov5_detection(sender, instance, created, **kwargs):
    # Saltamos cualquier inferencia; la imagen queda tal cual
    return


# -----------------------------------------------------------------
# 2. Cuando un Sample deja de estar disponible → informe diagnóstico
# -----------------------------------------------------------------
@receiver(post_save, sender=Sample)
def update_sample_availability(sender, instance, **kwargs):
    if not instance.available:
        run_diagnosis_report(instance.id)


# -----------------------------------------------------------------
# 3. Generar (o actualizar) el informe de diagnóstico
# -----------------------------------------------------------------
def run_diagnosis_report(sample_id):
    get_results(sample_id)


def get_results(sample_id):
    sample_images = SampleImage.objects.filter(sample=sample_id)

    detection_counter = Counter()
    total_of_images = len(sample_images)

    for sample_image in sample_images:
        # Protección: sin IA los resultados vienen vacíos o None
        if not sample_image.detection_results:
            continue
        for detection in sample_image.detection_results:
            detection_counter[detection['name']] += 1

    leukocytes = detection_counter['leukocytes']
    malaria_trophozoite = detection_counter['malaria_trophozoite']
    malaria_mature_trophozoite = detection_counter['malaria_mature_trophozoite']
    total_parasites = malaria_trophozoite + malaria_mature_trophozoite

    parasitemia_level = calculate_parasite_density(total_parasites, leukocytes)
    diagnosis_result = total_parasites > 0

    report = DiagnosisReport(
        sample_id=sample_id,
        date_published=timezone.now(),
        number_of_images=total_of_images,
        total_time=0,                     # ajusta si calculas duraciones
        parasites_count=total_parasites,
        leucocytes_count=leukocytes,
        parasitemia_level=parasitemia_level,
        diagnosis_result=diagnosis_result
    )
    report.save()

