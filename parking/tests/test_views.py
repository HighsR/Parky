import datetime
from http.client import responses

from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import time, timedelta

from ..forms import BookingForm, ParkingSpaceForm
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
    # map_view tests
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
    # book_parking tests
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
        data = {
            'booking_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d'),
            'start_hour': '10:00',
            'end_hour': '12:00',
        }
        with patch('parking.models.Booking.save', side_effect=ValidationError("Simulated Error")):
            response = self.client.post(reverse('book_parking', args=[self.parking.id]), data=data)

        self.assertTrue(response.context['form'].errors)
        self.assertIn("Simulated Error", str(response.context['form'].errors))

    def test_book_parking_get_request(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('book_parking', args=[self.parking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.context['form'], BookingForm)

    def test_my_booking_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('my_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,'parking/my_bookings.html')
        self.assertIn('bookings', response.context)

    # register tests
    def test_register_success(self):
        form_data = {
            'username': 'testuser',
            'password1': 'password123',
            'password2': 'password123',
        }
        response = self.client.post(reverse('register'),data=form_data)
        self.assertRedirects(response,reverse('map_view'))
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_register_get(self):
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'registration/register.html')
        self.assertIsInstance(response.context['form'], UserCreationForm)

    # add_parking_space tests
    def test_add_parking_space_success(self):
        self.client.force_login(self.user)
        form = {
            'name': 'Test',
            'city': 'test city',
            'address': 'test 12',
            'legal_declaration': True,
            'price_per_hour': 2,
        }

        response = self.client.post(reverse('add_parking_space'),data=form)
        self.assertRedirects(response,reverse('parking_added_success'))
        self.assertTrue(ParkingSpace.objects.filter(name='Test').exists())

    def test_add_parking_space_missing_lat_and_lon(self):
        self.client.force_login(self.user)
        self.mock_geocode.return_value=None
        form = {
            'name': 'Test Fail',
            'city': 'test city',
            'address': 'test 12',
            'legal_declaration': True,
            'price_per_hour': 2,
        }

        response = self.client.post(reverse('add_parking_space'),data=form)
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response, 'parking/add_parking_space.html')
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(ParkingSpace.objects.filter(name='Test Fail').exists())

    def test_add_parking_space_get(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('add_parking_space'))
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'parking/add_parking_space.html')
        self.assertIsInstance(response.context['form'], ParkingSpaceForm)

    def test_my_listings(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('my_listings'))
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'parking/my_listings.html')
        self.assertIsInstance(response.context['parkings'], QuerySet)
        self.assertEqual(response.context['parkings'].count(),1)
        self.assertIn(self.parking, response.context['parkings'])
