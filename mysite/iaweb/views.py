from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from .models import DiagnosisReport, SampleImage, Sample
from .serializers import DiagnosisReportSerializer, SampleImageSerializer, SampleSerializer


@api_view(['GET', 'PATCH'])
def view_sample(request):

    if request.method == 'GET':
        print("Fetching samples...")
        try:
            mydata = Sample.objects.filter(available=True)
            print(f"Fetched {mydata.count()} samples.")
            serializer = SampleSerializer(mydata, many=True)
            return Response(serializer.data)
        except Exception as e:
            print(f"Error: {str(e)}")  # Print the error for debugging
            return Response({"error": str(e)}, status=500)
    elif request.method == 'PATCH':
        sample_obj = Sample.objects.get(pk=request.data.get('id'))
        serializer = SampleSerializer(
            sample_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({'msg': 'Sample updated successfully', 'data': serializer.data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def view_image(request):
    serializer = SampleImageSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({'msg': 'Image created successfully', 'data': serializer.data}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ImageCreateView(generics.CreateAPIView):
    queryset = SampleImage.objects.all()
    serializer_class = SampleImageSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

'''
def index(request):
    return HttpResponse("Hello, world.")
@api_view(['GET'])
def get_diagnosis(request):
    mydata = DiagnosisReport.objects.all()
    serializer = DiagnosisReportSerializer(mydata, many=True)
    return Response(serializer.data)

c

class DiagnosisReportCreateView(generics.CreateAPIView):
    queryset = DiagnosisReport.objects.all()
    serializer_class = DiagnosisReportSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

'''
