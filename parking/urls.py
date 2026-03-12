from django.urls import path, include
from django.views.generic import TemplateView

from . import views

urlpatterns = [
    path('map/', views.map_view, name='map_view'),
    path('book/<int:parking_id>/', views.book_parking, name='book_parking'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('register/', views.register, name='register'),
    path('add-parking/', views.add_parking_space, name='add_parking_space'),
    path('parking-added/', TemplateView.as_view(template_name='parking/parking_added_success.html'), name='parking_added_success'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('edit-parking/<int:parking_id>/', views.edit_parking_space, name='edit_parking_space'),
    path('delete-parking/<int:parking_id>/', views.delete_parking_space,name='delete_parking_space'),
    path('manage-bookings', views.manage_seller_bookings, name='manage_seller_bookings'),
    path('accept-booking/<int:booking_id>/', views.booking_confirmation, name='booking_confirmation'),
    path('reject-booking/<int:booking_id>/', views.booking_rejection, name='booking_rejection'),
    path('profile/', views.profile_view, name='profile'),
]