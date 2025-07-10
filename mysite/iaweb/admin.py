from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Patient, Sample, DiagnosisReport, Disease, SampleImage, HealthCenter
from django.utils.html import format_html


@admin.register(Patient)
class PatientAdmin(ModelAdmin):
    list_display = ('id', 'name', 'age', 'sex', 'symptoms', 'date_published')
    search_fields = ('name', '')


@admin.register(Sample)
class SampleAdmin(ModelAdmin):
    list_display = ('id', 'available', 'sample_type',
                    'patient', 'health_center', 'date_published')
    list_filter = ('available', 'date_published')
    search_fields = ('sample_type', 'patient__name')


@admin.register(HealthCenter)
class HealthCenterAdmin(ModelAdmin):
    list_display = ('name', 'city', 'country', 'date_published')


@admin.register(Disease)
class DiseaseAdmin(ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(DiagnosisReport)
class DiagnosisReportAdmin(admin.ModelAdmin):
    # list_display = ('id', 'sample', 'date_published', 'number_of_images', 'diagnosis_result', 'sample_images_image_field')

    def change_view(self, request, object_id, form_url='', extra_context=None):
        # Get the DiagnosisReport instance
        diagnosis_report = self.get_object(request, object_id)
        if diagnosis_report:
            # Get related Sample
            sample = diagnosis_report.sample
            # Get all SampleImages related to the Sample
            sample_images = sample.images.all()
            # Add images to the context
            extra_context = extra_context or {}
            extra_context['sample_images'] = sample_images
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def sample_images_image_field(self, obj):
        images = obj.sample.images.all()
        image_tags = [
            format_html('<a href="{}" target="_blank"><img src="{}" width="50" height="50" /><br /></a>',
                        image.detected_image.url, image.detected_image.url)
            for image in images
        ]
        return format_html(' '.join(image_tags))
    sample_images_image_field.short_description = 'Sample Images'

    def get_list_display(self, request):
        # Add the custom field to the list display
        return ('id',
                'sample',
                'diseases',
                'parasites_count',
                'leucocytes_count',
                'parasitemia_level',
                'diagnosis_result',
                'sample_images_image_field',
                'number_of_images',
                'total_time',
                'date_published',)


@admin.register(SampleImage)
class SampleImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sample', 'image_thumbnail', 'date_published')
    actions = ['show_selected_images']

    def image_thumbnail(self, obj):
        """ Display thumbnail of the image in the admin list view. """
        if obj.image:
            return format_html(f'<img src="{obj.image.url}" style="height: 50px;" />')
        return '-'

    image_thumbnail.short_description = 'Image'

    def show_selected_images(self, request, queryset):
        """ Custom action to display selected images by their ID """
        images_html = ""
        for image_obj in queryset:
            images_html += f'<img src="{image_obj.image.url}" style="height: 150px; margin: 5px;" />'
        
        # Show the images as a response in the admin interface
        self.message_user(request, format_html(images_html))

    show_selected_images.short_description = 'Show selected images by ID'
