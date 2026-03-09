from django.db import models
from django.contrib.auth.models import User
from geopy.geocoders import Nominatim
from django.core.exceptions import ValidationError
from django.utils import timezone

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
                geolocator = Nominatim(user_agent="Parky_App_Project_HIT_Student" , timeout=10)
                address_string = f"{self.address}, {self.city}, Israel"
                location = geolocator.geocode(address_string)
                print(f"Geocoding address: {address_string} -> {location}")
                if location:
                    self.lat = location.latitude
                    self.lon = location.longitude
                else:
                    print(f"Could not geocode address: {address_string}")
            except Exception as e:
                print(f"Error geocoding address: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.address}"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'ממתין לאישור'),
        ('approved', 'מאושר'),
        ('canceled', 'בוטל'),
        ('completed', 'הסתיים'),
    ]
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.CASCADE, related_name='bookings')

    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    status = models.CharField(max_length=20,choices=STATUS_CHOICES, default='pending')

    def clean(self):
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")

        try:
            if self.parking_space and self.buyer:
                if timezone.now() > self.end_time or timezone.now() > self.start_time:
                    raise ValidationError("Booking times must be in the future.")

                if self.parking_space.bookings.filter(
                    status__in=['pending', 'approved'],start_time__lt=self.end_time,end_time__gt=self.start_time).exclude(id=self.id).exists():
                    raise ValidationError("This parking space is already booked for the selected time range.")
        except (ParkingSpace.DoesNotExist, User.DoesNotExist):
            pass
    def __str__(self):
        return f"Booking by {self.buyer.username} for {self.parking_space.name} from {self.start_time} to {self.end_time} - Status: {self.status}"

