from django.shortcuts import render
from .models import ParkingSpace

def map_view(request):
    parkings=ParkingSpace.objects.filter(is_active=True, lat__isnull=False, lon__isnull=False)
    return render(request, 'parking/map.html', {'parkings': parkings})