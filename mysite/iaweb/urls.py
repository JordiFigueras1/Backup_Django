from django.urls import path
from . import views


urlpatterns = [
    #path("", views.index, name="index"),
    #path('find-diagnosis/', views.get_diagnosis, name='findByDiagnosis'),
    #path('report/', views.DiagnosisReportCreateView.as_view(), name='diagnosis_report_create'),
    path('sample/', views.view_sample, name='Sample'),
    path('image/', views.view_image, name='Image'),
    path('send-images/', views.ImageCreateView.as_view(), name='Images'),

]
