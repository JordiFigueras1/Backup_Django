from django.contrib import admin, messages
from django.utils.html import format_html

# ─── helpers para stitching ──────────────────────────────────────
from .utils_stitch import stitch_circular, stitch_cropped, save_mosaic

from .models import (
    Patient, Sample, DiagnosisReport, Disease,
    SampleImage, HealthCenter, SampleImageVisualizer
)

# =====================================================================
# PACIENTES
# =====================================================================
from unfold.admin import ModelAdmin


@admin.register(Patient)
class PatientAdmin(ModelAdmin):
    list_display = ('id', 'name', 'age', 'sex', 'symptoms', 'date_published')
    search_fields = ('name',)


# =====================================================================
# MUESTRAS  (ahora con acciones de stitching)
# =====================================================================
@admin.register(Sample)
class SampleAdmin(ModelAdmin):
    list_display = ('id', 'available', 'sample_type',
                    'patient', 'health_center', 'date_published')
    list_filter = ('available', 'date_published')
    search_fields = ('sample_type', 'patient__name')

    # ─── acciones de stitching ───────────────────────────────────
    @admin.action(description="Stitch circular mosaic")
    def make_stitch_circular(self, request, queryset):
        for sample in queryset:
            try:
                pano = stitch_circular(sample)
                save_mosaic(sample, pano, "circular")
                self.message_user(
                    request,
                    f"Mosaico circular creado para {sample.id}",
                    level=messages.SUCCESS
                )
            except Exception as exc:
                self.message_user(
                    request,
                    f"{sample.id}: {exc}",
                    level=messages.ERROR
                )

    @admin.action(description="Stitch cropped mosaic")
    def make_stitch_cropped(self, request, queryset):
        for sample in queryset:
            try:
                pano = stitch_cropped(sample)
                save_mosaic(sample, pano, "cropped")
                self.message_user(
                    request,
                    f"Mosaico cropped creado para {sample.id}",
                    level=messages.SUCCESS
                )
            except Exception as exc:
                self.message_user(
                    request,
                    f"{sample.id}: {exc}",
                    level=messages.ERROR
                )

    actions = ["make_stitch_circular", "make_stitch_cropped"]


# =====================================================================
# CENTROS DE SALUD
# =====================================================================
@admin.register(HealthCenter)
class HealthCenterAdmin(ModelAdmin):
    list_display = ('name', 'city', 'country', 'date_published')


# =====================================================================
# ENFERMEDADES
# =====================================================================
@admin.register(Disease)
class DiseaseAdmin(ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


# =====================================================================
# INFORMES
# =====================================================================
@admin.register(DiagnosisReport)
class DiagnosisReportAdmin(admin.ModelAdmin):

    def change_view(self, request, object_id, form_url='', extra_context=None):
        diagnosis_report = self.get_object(request, object_id)
        if diagnosis_report:
            sample = diagnosis_report.sample
            sample_images = sample.images.all()
            extra_context = extra_context or {}
            extra_context['sample_images'] = sample_images
        return super().change_view(request, object_id, form_url,
                                   extra_context=extra_context)

    def sample_images_image_field(self, obj):
        images = obj.sample.images.all()
        image_tags = [
            format_html(
                '<a href="{0}" target="_blank"><img src="{0}" width="50" '
                'height="50" /><br /></a>',
                image.detected_image.url
            ) for image in images
        ]
        return format_html(' '.join(image_tags))

    sample_images_image_field.short_description = 'Sample Images'

    def get_list_display(self, request):
        return (
            'id', 'sample', 'diseases',
            'parasites_count', 'leucocytes_count',
            'parasitemia_level', 'diagnosis_result',
            'sample_images_image_field',
            'number_of_images', 'total_time', 'date_published',
        )


# =====================================================================
# IMÁGENES DE MUESTRA (listado clásico)
# =====================================================================
@admin.register(SampleImage)
class SampleImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sample', 'image_thumbnail', 'date_published')
    actions = ['show_selected_images']

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height: 50px;" />',
                obj.image.url
            )
        return '-'

    image_thumbnail.short_description = 'Image'

    def show_selected_images(self, request, queryset):
        images_html = ''.join(
            f'<img src="{img.image.url}" style="height: 150px; margin: 5px;" />'
            for img in queryset
        )
        self.message_user(request, format_html(images_html))

    show_selected_images.short_description = 'Show selected images by ID'


# =====================================================================
# ────────  VISUALIZER   ─────────────────────────────────────────────
# =====================================================================
@admin.register(SampleImageVisualizer)
class SampleImageVisualizerAdmin(admin.ModelAdmin):
    """
    Vista especial que muestra solo las sub-imágenes de una muestra
    seleccionada mediante un <select>.
    """
    change_list_template = "admin/iaweb/sample_visualizer_changelist.html"

    list_display = ('thumbnail', 'id', 'sample',
                    'patient_name', 'date_published')
    list_select_related = ('sample__patient',)
    list_per_page = 300
    ordering = ('sample', 'id')
    list_filter = ()
    actions = None

    # ────────────── helpers ──────────────
    def thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px;border-radius:4px;" />',
                obj.image.url
            )
        return '-'

    thumbnail.short_description = 'Image'

    def patient_name(self, obj):
        return obj.sample.patient.name

    patient_name.short_description = 'Patient'

    # ────────────── filtrado por muestra ──────────────
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        sample_id = request.GET.get("sample")
        if sample_id:
            qs = qs.filter(sample_id=sample_id)
        else:
            first_sample = Sample.objects.order_by("date_published").first()
            if first_sample:
                qs = qs.filter(sample=first_sample)
        return qs

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        samples = Sample.objects.select_related("patient")\
                                .order_by("-date_published")
        extra_context["samples"] = samples
        extra_context["selected_sample"] = request.GET.get(
            "sample",
            samples.first().id if samples else None
        )
        return super().changelist_view(request,
                                       extra_context=extra_context)
