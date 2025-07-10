# serializers.py

from rest_framework import serializers
from .models import DiagnosisReport, SampleImage, Sample
import base64
from django.core.files.base import ContentFile


class Base64ImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if isinstance(data, str) and data.startswith('data:image'):
            # Parse the base64 image string
            format, imgstr = data.split(';base64,')
            ext = format.split('/')[-1]
            data = ContentFile(base64.b64decode(imgstr), name='temp.' + ext)
        return super().to_internal_value(data)


class SampleImageSerializer(serializers.ModelSerializer):

    image = Base64ImageField()

    class Meta:
        model = SampleImage
        fields = ['id', 'sample', 'image', 'date_published']


class SampleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sample
        fields = ['id', 'patient', 'sample_type', 'date_published',
                  'available', 'images']


class DiagnosisReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DiagnosisReport
        fields = ['id', 'sample', 'diseases', 'date_published',
                  'number_of_images', 'total_time',
                  'parasites_count', 'leucocytes_count', 'parasitemia_level',
                  'diagnosis_result']
