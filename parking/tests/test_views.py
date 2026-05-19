import datetime

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import time, timedelta

from ..forms import BookingForm
from ..models import ParkingSpace, Booking, Profile

class ParkingViewsTest(TestCase):
    def setUp(self):
        self.patcher = patch('geopy.geocoders.Nominatim.geocode')
        self.mock_geocode = self.patcher.start()
        mock_location = MagicMock()
        mock_location.latitude = 32.0853
        mock_location.longitude = 34.7818
        self.mock_geocode.return_value = mock_location

        self.user = User.objects.create_user(username="test_user", password="password123")
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.profile.phone_number = "0501234567"
        self.profile.license_plate = "1234567"
        self.profile.save()

        self.owner = User.objects.create_user(username="owner_user", password="password123")

        self.parking = ParkingSpace.objects.create(
            owner=self.owner,
            name="Central Holon Parking",
            city="Holon",
            address="Golomb 52",
            price_per_hour=10.0,
            legal_declaration=True
        )

    def tearDown(self):
        self.patcher.stop()

    def get_messages(self, response):
        return [m.message for m in response.context.get('messages', [])]

    def test_map_view_accessible_by_everyone(self):
        response = self.client.get(reverse('map_view'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'parking/map.html')
        self.assertIn(self.parking, response.context['parkings'])

    def test_map_view_filters_parking_spaces(self):
        inactive_parking = ParkingSpace.objects.create(
            owner=self.owner,
            name="Inactive",
            city="Holon",
            address="Golomb 50",
            price_per_hour=10,
            legal_declaration=True,
            is_active=False
        )

        no_coords_parking = ParkingSpace.objects.create(
            owner=self.owner,
            name="No Coords",
            city="Holon",
            address="Golomb 54",
            price_per_hour=10,
            legal_declaration=True,
        )
        ParkingSpace.objects.filter(id=no_coords_parking.id).update(lat=None, lon=None)
        response = self.client.get(reverse('map_view'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.parking, response.context['parkings'])

        self.assertNotIn(inactive_parking, response.context['parkings'])
        self.assertNotIn(no_coords_parking, response.context['parkings'])

    def test_add_parking_view_redirects_anonymous_user(self):
        response = self.client.get(reverse('add_parking_space'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_mark_completed_bookings(self):
        from ..views import mark_completed_bookings
        now = timezone.now()
        past_booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=now - timedelta(hours=3),
            end_time=now - timedelta(hours=1),
            status='approved'
        )
        future_booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=3),
            status='approved'
        )
        canceled_booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=now - timedelta(hours=5),
            end_time=now - timedelta(hours=4),
            status='canceled'
        )
        updated_count = mark_completed_bookings()
        self.assertEqual(updated_count, 1)

        past_booking.refresh_from_db()
        future_booking.refresh_from_db()
        canceled_booking.refresh_from_db()

        self.assertEqual(past_booking.status, 'completed')
        self.assertEqual(future_booking.status, 'approved')
        self.assertEqual(canceled_booking.status, 'canceled')

    def test_booking_fails_if_no_phone(self):
        self.profile.phone_number = None
        self.profile.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('book_parking', args=[self.parking.id]), follow=True)
        messages = self.get_messages(response)
        self.assertIn('בשביל לבצע הזמנה, עליך להוסיף מספר טלפון בפרופיל שלך.', messages)

    def test_booking_fails_if_no_licence_plate(self):
        self.profile.license_plate=None
        self.profile.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('book_parking', args=[self.parking.id]), follow=True)
        messages = self.get_messages(response)
        self.assertIn('בשביל לבצע הזמנה, עליך להוסיף מספר רכב בפרופיל שלך.', messages)

    def test_booking_fails_owner_equals_buyer(self):
        self.parking.owner=self.user
        self.parking.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('book_parking', args=[self.parking.id]),HTTP_REFERER='/map/',follow=True)
        messages = self.get_messages(response)
        self.assertIn('לא ניתן להזמין את החניות שלך', messages)

    def test_book_parking_success(self):
        with patch('parking.views.send_user_notification') as mock_send_notif:
            self.client.force_login(self.user)
            form_data = {
                'booking_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                'start_hour': '10:00',
                'end_hour': '12:00',
            }
            response = self.client.post(reverse('book_parking', args=[self.parking.id]), data=form_data)
            self.assertTrue(Booking.objects.filter(buyer=self.user, parking_space=self.parking).exists())
            self.assertTrue(mock_send_notif.called)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, 'parking/booking_success.html')

    def test_book_parking_fail(self):
        self.client.force_login(self.user)
        with patch('parking.views.send_user_notification') as mock_send_notif:
            self.client.force_login(self.user)
            form_data = {
                'booking_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
                'start_hour': '14:00',
                'end_hour': '12:00',
            }
            response = self.client.post(reverse('book_parking', args=[self.parking.id]), data=form_data)
            self.assertFalse(Booking.objects.filter(buyer=self.user, parking_space=self.parking).exists())
            self.assertEqual(response.status_code, 200)
            self.assertIn('form', response.context)
            self.assertTrue(response.context['form'].errors)

    def test_book_parking_validation_error_triggers_except(self):
        self.client.force_login(self.user)
        bad_data = {
            'booking_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_hour': '14:00',
            'end_hour': '10:00',
        }
        with patch('parking.models.Booking.clean', side_effect=ValidationError("Simulated Error")):
            response = self.client.post(reverse('book_parking', args=[self.parking.id]), data=bad_data)
            self.assertTrue(response.context['form'].non_field_errors())

    def test_book_parking_get_request(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('book_parking', args=[self.parking.id]))

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], BookingForm)