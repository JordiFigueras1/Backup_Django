import uuid
from django.db import models


class Patient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, verbose_name="Patient Name")
    age = models.IntegerField(verbose_name="Patient Age")
    sex = models.CharField(max_length=10, choices=[('M', 'Male'), ('F', 'Female')], verbose_name="Sex")
    symptoms = models.TextField(verbose_name="Symptoms", blank=True, null=True)
    observations = models.TextField(verbose_name="Observations", blank=True, null=True)
    date_published = models.DateTimeField("Date Published")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ['name']


class HealthCenter(models.Model):
    name = models.CharField(max_length=100, verbose_name="Health Center Name")
    city = models.CharField(max_length=100, verbose_name="Health Center City")
    country = models.CharField(max_length=100, verbose_name="Health Center Country")
    date_published = models.DateTimeField("Date Published")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Health Center"
        verbose_name_plural = "Health Centers"
        ordering = ['name']


class Sample(models.Model):
    BLOOD = 'Blood'
    URINE = 'Urine'
    SAMPLE_TYPE_CHOICES = [
        (BLOOD, 'Blood'),
        (URINE, 'Urine'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.PROTECT, related_name='patient')
    sample_type = models.CharField(max_length=5, choices=SAMPLE_TYPE_CHOICES)
    health_center = models.ForeignKey(
        HealthCenter, on_delete=models.PROTECT, related_name='health_center', default=1)
    date_published = models.DateTimeField("Date Published")
    available = models.BooleanField(default=True, verbose_name="Available")

    def __str__(self):
        return f"{self.patient.id} - {self.patient.name}"

    class Meta:
        verbose_name = "Sample"
        verbose_name_plural = "Samples"
        ordering = ['-date_published']


class SampleImage(models.Model):

    def sample_image_upload_to(instance, filename):
        extension = filename.split('.')[-1]
        return f"images/{instance.id}.{extension}"

    def sample_image_upload_to_detection(instance, filename):
        extension = filename.split('.')[-1]
        return f"images/{instance.id}_detection.{extension}"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.ForeignKey(Sample, related_name='images',
                               on_delete=models.CASCADE, verbose_name="Sample")
    image = models.ImageField(upload_to=sample_image_upload_to)
    date_published = models.DateTimeField("Date Published", auto_now_add=True)
    detection_results = models.JSONField(null=True, blank=True)
    detected_image = models.ImageField(
        upload_to=sample_image_upload_to_detection, null=True, blank=True)

    def __str__(self):
        return f"Images for {self.sample.id}"

    class Meta:
        verbose_name = "Image"
        verbose_name_plural = "Images"
        ordering = ['-date_published']


# ──────────────────────────────────────────────────────────────────────────────
# NUEVO  ➜  proxy-model para el “Visualizer” del admin
# ──────────────────────────────────────────────────────────────────────────────
class SampleImageVisualizer(SampleImage):
    """Proxy que usa la misma tabla de SampleImage pero se mostrará como
    'Visualizer' en la barra lateral del admin."""
    class Meta:
        proxy = True
        verbose_name = "Visualizer"
        verbose_name_plural = "Visualizer"


class Disease(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Disease"
        verbose_name_plural = "Diseases"
        ordering = ['name']


class DiagnosisReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sample = models.ForeignKey(
        Sample, on_delete=models.CASCADE, related_name='Sample')
    diseases = models.ForeignKey(
        Disease, on_delete=models.PROTECT, related_name='Diseases', default=1)
    date_published = models.DateTimeField("Date Published")
    number_of_images = models.IntegerField(
        default=0, verbose_name="Number of Images")
    total_time = models.IntegerField(
        default=0, verbose_name="Total Time (minutes)")
    parasites_count = models.IntegerField(
        default=0, verbose_name="Parasites Count")
    leucocytes_count = models.IntegerField(
        default=0, verbose_name="Leucocytes Count")
    parasitemia_level = models.IntegerField(
        default=0, verbose_name="Parasitemia Level")
    diagnosis_result = models.BooleanField(
        default=False, verbose_name="Diagnosis Result")

    def __str__(self):
        return f"{self.id}"

    class Meta:
        verbose_name = "Diagnosis Report"
        verbose_name_plural = "Diagnosis Reports"
        ordering = ['-date_published']
