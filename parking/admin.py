from django.contrib import admin
from .models import ParkingSpace, Booking

@admin.register(ParkingSpace)
class ParkingSpaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'address', 'price_per_hour', 'lat', 'lon', 'is_active')

    search_fields = ('name', 'city', 'address')

    list_filter = ('is_active','city')

    readonly_fields = ('lat', 'lon')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('buyer', 'parking_space', 'start_time', 'end_time', 'status')
    list_filter = ('status',)