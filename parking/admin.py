from django.contrib import admin
from .models import ParkingSpace, Booking, Report, Notification


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
    search_fields = ('parking_space', 'start_time', 'end_time')
    readonly_fields = ('start_time', 'end_time')

@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('parking_space', 'reporter', 'reason', 'created_at')
    list_filter = ('is_resolved','reason')
    search_fields = ('description', 'reporter__username')
    readonly_fields = ('created_at', 'reason','reporter')

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('message_title', 'receiver', 'notification_type', 'is_read', 'created_at')
    list_filter = ('is_read' ,'notification_type', 'created_at')
    search_fields = ('message_title', 'message_content', 'receiver__username')