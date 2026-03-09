from django.db import models
from django.contrib.auth.models import User
from geopy.geocoders import Nominatim

class ParkingSpace(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    price_per_hour=models.DecimalField(max_digits=10, decimal_places=2)
    instructions = models.TextField(blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.address and (self.lat is None or self.lon is None):
            try:
                geolocator = Nominatim(user_agent="parky_app")
                location = geolocator.geocode(f"{self.address}, {self.city}")

                if location:
                    self.lat = location.latitude
                    self.lon = location.longitude
            except Exception as e:
                print(f"Error geocoding address: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.address}"

class Booking(models.Model):
