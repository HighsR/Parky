import requests
from django.contrib.auth.forms import UserCreationForm
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..forms import BookingForm, ParkingSpaceForm, ReportForm, BookingRatingForm, ProfileUpdateForm
from ..models import ParkingSpace, Profile


class ParkingFormsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_user", password="password123")
        self.owner = User.objects.create_user(username="owner_user", password="password123")
        self.profile = Profile.objects.create(user=self.user, phone_number="0501234567", license_plate="1234567")
        self.parking = ParkingSpace.objects.create(
            owner=self.owner,
            name="Test Parking",
            city="Holon",
            address="Street 1",
            price_per_hour=10.0,
            legal_declaration=True
        )
    def test_no_legal_declaration(self):
        form_data = {
            'name': 'Test Parking',
            'city': 'Holon',
            'address': 'Street 1',
            'price_per_hour': 10.0,
            'legal_declaration': False,
        }
        form = ParkingSpaceForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('legal_declaration', form.errors)
        self.assertEqual(form.errors['legal_declaration'],['עליך לאשר את ההצהרה המשפטית כדי להוסיף חניה למערכת.'])

    def test_clean_license_plate_works(self):
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'result': {'records': [{'mispar_rechev': '9999999'}]}}
            mock_get.return_value = mock_response
            form = ProfileUpdateForm(data={'license_plate': '9999999'}, instance=self.profile)
            self.assertTrue(form.is_valid())
            mock_get.assert_called()
            self.assertIn('9999999', mock_get.call_args[1]['params']['filters'])

    @override_settings(PHONENUMBER_DEFAULT_REGION='IL')
    def test_clean_license_plate_the_same_plate(self):
        with patch('requests.get') as mock_get:

            form = ProfileUpdateForm(data={'license_plate': '1234567', 'phone_number': '0501234567'}, instance=self.profile)
            form.cleaned_data = {'license_plate': '1234567'}
            result = form.clean_license_plate()
            self.assertEqual(result, '1234567')
            mock_get.assert_not_called()

    def test_clean_license_plate_second_api_success(self):
        with patch('requests.get') as mock_get:
            resp_empty = MagicMock(status_code=200)
            resp_empty.json.return_value = {'result': {'records': []}}
            resp_success = MagicMock(status_code=200)
            resp_success.json.return_value = {'result': {'records': [{'mispar_rechev': '9999999'}]}}
            mock_get.side_effect = [resp_empty, resp_success]
            new_plate = '9999999'
            form = ProfileUpdateForm(data={'license_plate': new_plate}, instance=self.profile)
            form.cleaned_data = {'license_plate': new_plate}
            result = form.clean_license_plate()
            self.assertEqual(result, new_plate)
            self.assertEqual(mock_get.call_count, 2)

    def test_clean_license_plate_first_api_crash(self):
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network Error")
            new_plate = '9999999'
            form = ProfileUpdateForm(data={'license_plate': new_plate}, instance=self.profile)
            form.cleaned_data = {'license_plate': new_plate}
            with self.assertRaises(ValidationError) as context:
                form.clean_license_plate()
            self.assertIn('אירעה שגיאה בעת אימות', str(context.exception))

    def test_clean_license_plate_second_api_crash(self):
        with patch('requests.get') as mock_get:
            resp_empty = MagicMock(status_code=200)
            resp_empty.json.return_value = {'result': {'records': []}}
            mock_get.side_effect = [resp_empty, requests.RequestException("Network Error")]
            new_plate = '9999999'
            form = ProfileUpdateForm(data={'license_plate': new_plate}, instance=self.profile)
            form.cleaned_data = {'license_plate': new_plate}
            with self.assertRaises(ValidationError) as context:
                form.clean_license_plate()
            self.assertIn('אירעה שגיאה בעת אימות', str(context.exception))
            self.assertEqual(mock_get.call_count, 2)

    def test_clean_license_plate_not_found_at_all(self):
        with patch('requests.get') as mock_get:
            resp_empty = MagicMock(status_code=200)
            resp_empty.json.return_value = {'result': {'records': []}}
            mock_get.side_effect = [resp_empty, resp_empty]
            new_plate = '9999999'
            form = ProfileUpdateForm(data={'license_plate': new_plate}, instance=self.profile)
            form.cleaned_data = {'license_plate': new_plate}
            with self.assertRaises(ValidationError) as context:
                form.clean_license_plate()
            self.assertIn('מספר רכב לא נמצא במאגר', str(context.exception))
            self.assertEqual(mock_get.call_count, 2)