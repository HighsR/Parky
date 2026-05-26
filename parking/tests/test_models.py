import datetime

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import date, time,timedelta
from django.utils.timezone import make_aware

from ..models import ParkingSpace, Booking, Profile, Report, Notification

class ParkinSpaceTest(TestCase):
    def setUp(self):
        self.patcher = patch('geopy.geocoders.Nominatim.geocode')
        self.mock_geocode = self.patcher.start()
        mock_location = MagicMock()
        mock_location.latitude = 32.0853
        mock_location.longitude = 34.7818
        self.mock_geocode.return_value = mock_location

        self.user=User.objects.create_user(username="user_test",password="12345678")
        self.parking=ParkingSpace.objects.create(
            owner=self.user,
            name="Test Space",
            city="Holon",
            address="Golomb 52",
            price_per_hour=5.5,
            legal_declaration=True
        )

    def tearDown(self):
        self.patcher.stop()

    def test_legal_declaration(self):
        self.assertTrue(self.parking.legal_declaration)

    def test_cannot_save_without_legal_confirm(self):
        false_space=ParkingSpace(
            owner=self.user,
            name="Test",
            address="Golomb 52",
            legal_declaration=False,
            price_per_hour = 5.5
        )
        with self.assertRaisesMessage(ValidationError,"חובה לאשר הצהרה חוקית"):
            false_space.full_clean()

        self.assertTrue(self.mock_geocode.called)

    def test_negative_price(self):
        negative_price_space=ParkingSpace(
            owner=self.user,
            name="Test",
            address="Golomb 52",
            price_per_hour=-1,
            legal_declaration=True
        )
        with self.assertRaisesMessage(ValidationError,"המחיר לא יכול להיות שלילי"):
            negative_price_space.full_clean()

    def test_start_date_after_end_date(self):
        bad_date_space=ParkingSpace(
            owner=self.user,
            name="Test",
            address="Golomb 52",
            city="Holon",
            start_date=date(2025, 11, 12),
            end_date=date(2025, 11, 11),
            legal_declaration=True
        )
        with self.assertRaisesMessage(ValidationError,"תאריך הסיום לא יכול להיות מוקדם מתאריך ההתחלה."):
            bad_date_space.full_clean()

    def test_available_from_after_available_to(self):
        bad_time_space = ParkingSpace(
            owner=self.user,
            name="Time Test",
            address="Golomb 52",
            price_per_hour=10,
            available_from=time(14, 0),
            available_to=time(10, 0),
            legal_declaration=True
        )
        with self.assertRaisesMessage(ValidationError,"זמן סיום לא יכול להיות מוקדם מזמן ההתחלה."):
            bad_time_space.full_clean()

    def test_cascade_delete_user(self):
        self.user.delete()
        self.assertEqual(ParkingSpace.objects.count(), 0)

    def test_string_representation(self):
        expected_name = f"{self.parking.name} - {self.parking.address}"
        self.assertEqual(str(self.parking), expected_name)

    def test_could_not_geocode(self):
        self.mock_geocode.return_value = None
        bad_geocode=ParkingSpace(
            owner=self.user,
            name="Test",
            city="Test City",
            address="Bad 12",
            price_per_hour=1,
            legal_declaration=True,
        )
        with self.assertRaises(ValidationError):
            bad_geocode.save()

class BookingTest(TestCase):
    def setUp(self):
        self.patcher = patch('geopy.geocoders.Nominatim.geocode')
        self.mock_geocode = self.patcher.start()
        mock_location = MagicMock()
        mock_location.latitude = 32.0853
        mock_location.longitude = 34.7818
        self.mock_geocode.return_value = mock_location

        self.seller=User.objects.create_user(username="seller_test",password="12345678")
        self.buyer=User.objects.create_user(username="buyer_test",password="12345678")
        self.parking = ParkingSpace.objects.create(
            owner=self.seller,
            name="Test Space",
            city="Holon",
            address="Golomb 52",
            price_per_hour=5.5,
            legal_declaration=True
        )

    def tearDown(self):
        self.patcher.stop()

    def test_already_booked(self):
        start_time_1 = timezone.now() + timedelta(days=1)
        end_time_1 = start_time_1 + timedelta(hours=2)
        Booking.objects.create(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=start_time_1,
            end_time=end_time_1,
            status='pending',
        )
        test_buyer = User.objects.create_user(username="test_buyer", password="12345678")
        already_booked_booking=Booking(
            buyer=test_buyer,
            parking_space=self.parking,
            start_time=start_time_1,
            end_time=end_time_1
        )
        with self.assertRaisesMessage(ValidationError," החניה כבר הוזמנה לתקופה זו. אנא בחר זמן אחר."):
            already_booked_booking.full_clean()

    def test_missing_start_time_and_end_time(self):
        missing_times_booking=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError,"זמני התחלה וסיום הם שדות חובה."):
            missing_times_booking.full_clean()

    def test_start_time_before_end_time(self):
        bad_times_booking=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=timezone.now(),
            end_time=timezone.now()-timedelta(hours=2),
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError,"זמן ההתחלה חייב להיות לפני זמן הסיום."):
            bad_times_booking.full_clean()

    def test_already_passed_times(self):
        past_times_booking=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError,"לא ניתן להזמין חניה לזמן שעבר."):
            past_times_booking.full_clean()

    def test_bad_start_date(self):
        future_start_date = (timezone.now() + timedelta(days=7)).date()
        self.parking.start_date = future_start_date
        self.parking.save()

        bad_date_booking=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(days=2),
            end_time=timezone.now() + timedelta(days=2) + timedelta(hours=2),
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError,f"החניה זמינה החל מ-{future_start_date}"):
            bad_date_booking.full_clean()

    def test_bad_end_date(self):
        future_end_date = (timezone.now() + timedelta(days=3)).date()
        self.parking.end_date = future_end_date
        self.parking.save()

        late_booking = Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(days=5),
            end_time=timezone.now() + timedelta(days=5) + timedelta(hours=2),
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError, f"החניה זמינה עד {future_end_date}"):
            late_booking.full_clean()

    def test_bad_times(self):
        self.parking.available_from = time(8, 0)
        self.parking.available_to = time(18, 0)
        self.parking.save()
        future_date = timezone.now() + timedelta(days=1)
        bad_time=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=future_date.replace(hour=7, minute=0, second=0),
            end_time=future_date+timedelta(hours=2),
            status='pending',
        )
        with self.assertRaisesMessage(ValidationError,f'החנייה זמינה רק בין השעות {self.parking.available_from.strftime("%H:%M")} ל-{self.parking.available_to.strftime("%H:%M")}.'):
            bad_time.full_clean()

    def test_bad_day(self):
        self.parking.available_mon = False
        self.parking.save()
        future_date = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
        while future_date.weekday() != 0:
            future_date += timedelta(days=1)
        booking = Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=future_date,
            end_time=future_date + timedelta(hours=2)
        )
        with self.assertRaisesMessage(ValidationError, "החניה לא זמינה בימי Monday"):
            booking.full_clean()

    def test_missing_foreign_keys_handled_gracefully(self):
        missing_parking_booking=Booking(
            buyer=self.buyer,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            status='pending',
        )
        with self.assertRaises(ValidationError) as context:
            missing_parking_booking.full_clean()
        self.assertIn('parking_space', context.exception.message_dict)

    def test_string_representation(self):
        booking=Booking(
            buyer=self.buyer,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=2),
            status='pending',
        )
        expected=f"Booking by {self.buyer.username} for {self.parking.name} from {booking.start_time} to {booking.end_time} - Status: {booking.status}"
        self.assertEqual(str(booking), expected)

class ProfileTest(TestCase):
    def test_string_representation(self):
        user=User.objects.create_user(username="user_test",password="12345678")
        profile=Profile.objects.create(user=user)
        expected=f"{user.username} Profile"
        self.assertEqual(str(profile), expected)

class ReportTest(TestCase):
    def test_string_representation(self):
        self.patcher = patch('geopy.geocoders.Nominatim.geocode')
        self.mock_geocode = self.patcher.start()
        mock_location = MagicMock()
        mock_location.latitude = 32.0853
        mock_location.longitude = 34.7818
        self.mock_geocode.return_value = mock_location
        user=User.objects.create_user(username="user_test",password="12345678")
        seller=User.objects.create_user(username="seller_test",password="12345678")
        parking=ParkingSpace.objects.create(
            owner=seller,
            name="Test Space",
            city="Holon",
            address="Golomb 52",
            price_per_hour=5.5,
            legal_declaration=True
        )
        report=Report.objects.create(parking_space=parking,reporter=user)
        expected=f"דיווח על חניה {parking.id} מאת {user}"
        self.assertEqual(str(report), expected)

class NotificationTest(TestCase):
    def test_string_representation(self):
        receiver=User.objects.create_user(username="receiver_test",password="12345678")
        message_title="Test"
        notification=Notification.objects.create(message_title=message_title,receiver=receiver)
        expected=f"{message_title} - {receiver.username}"
        self.assertEqual(str(notification), expected)
