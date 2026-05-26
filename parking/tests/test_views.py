from django.contrib.auth.forms import UserCreationForm
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.db.models import QuerySet
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch, MagicMock
from datetime import timedelta

from ..forms import BookingForm, ParkingSpaceForm, ReportForm, BookingRatingForm
from ..models import ParkingSpace, Booking, Profile, Notification


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

    # edit_parking_space tests
    def test_edit_parking_space_works(self):
        self.client.force_login(self.owner)
        form = {
            'name': 'Edit Test',
            'city': 'test city',
            'address': 'test 12',
            'legal_declaration': True,
            'price_per_hour': 2,
        }
        response = self.client.post(reverse('edit_parking_space',args= [self.parking.id]),data=form)
        self.assertRedirects(response,reverse('my_listings'))
        self.parking.refresh_from_db()
        self.assertTrue(ParkingSpace.objects.filter(name='Edit Test').exists())

    def test_edit_parking_space_get(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('edit_parking_space',args= [self.parking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,'parking/add_parking_space.html')
        self.assertIsInstance(response.context['form'], ParkingSpaceForm)
        self.assertTrue(response.context.get('edit_mode'))
        self.assertEqual(response.context['parking_space'], self.parking)

    # delete_parking_space tests
    def test_delete_parking_space_works(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('delete_parking_space',args=  [self.parking.id]))
        self.assertRedirects(response,reverse('my_listings'))
        self.assertFalse(ParkingSpace.objects.filter(id=self.parking.id).exists())

    def test_delete_parking_space_get_method_not_allowed(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('delete_parking_space',args=  [self.parking.id]))
        self.assertEqual(response.status_code, 405)

    # manage_seller_bookings tests
    def test_manage_seller_bookings(self):
        self.client.force_login(self.owner)
        active_booking=Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now()+timedelta(hours=2),
            end_time=timezone.now()+timedelta(hours=4)
        )
        canceled_booking=Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now()-timedelta(hours=5),
            end_time=timezone.now()-timedelta(hours=4),
            status='canceled'
        )
        response = self.client.get(reverse('manage_seller_bookings'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,'parking/manage_bookings.html')
        self.assertIn(active_booking,response.context['active_bookings'])
        self.assertIn(canceled_booking,response.context['canceled_bookings'])

    # booking_confirmation tests
    def test_booking_confirmation_works(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=2),
            end_time=timezone.now() + timedelta(hours=4)
        )
        with patch('parking.views.send_user_notification') as mock_send_notif:
            response = self.client.post(reverse('booking_confirmation',args=[booking.id]))
            notification = Notification.objects.get(receiver=self.user, notification_type="order_confirmed")
            mock_send_notif.assert_called_once_with(
                user_id=self.user.id,
                message=notification.message_content,
                title=notification.message_title,
                notif_type=notification.notification_type,
                target_url=notification.target_url
            )
        booking.refresh_from_db()
        self.assertTrue(Notification.objects.filter(receiver=self.user, notification_type="order_confirmed").exists())
        self.assertEqual(booking.status,'approved')
        self.assertRedirects(response,reverse('manage_seller_bookings'))
        self.assertEqual(notification.message_title, "הזמנה אושרה!")
        self.assertIn(self.parking.address, notification.message_content)

    def test_booking_confirmation_get(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=2),
            end_time=timezone.now() + timedelta(hours=4)
        )
        response = self.client.get(reverse('booking_confirmation',args=[booking.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response,'parking/accept_booking.html')
        self.assertEqual(response.context['booking'], booking)

    # booking_rejection tests
    def test_booking_rejection_works_owner(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4)
        )
        with patch('parking.views.send_user_notification') as mock_send_notif:
            response = self.client.post(reverse('booking_rejection',args=[booking.id]))
            notification = Notification.objects.get(receiver=self.user, notification_type="order_canceled")
            mock_send_notif.assert_called_once_with(
                user_id=self.user.id,
                message=notification.message_content,
                title=notification.message_title,
                notif_type=notification.notification_type,
                target_url=notification.target_url
            )
            booking.refresh_from_db()
            self.assertTrue(Notification.objects.filter(receiver=self.user, notification_type="order_canceled").exists())
            self.assertEqual(booking.status, 'canceled')
            self.assertRedirects(response, reverse('manage_seller_bookings'))
            self.assertEqual(notification.message_title, "הזמנה בוטלה!")
            self.assertIn(self.parking.name, notification.message_content)

    def test_booking_rejection_works_buyer(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4)
        )
        with patch('parking.views.send_user_notification') as mock_send_notif:
            response = self.client.post(reverse('booking_rejection',args=[booking.id]))
            notification = Notification.objects.get(receiver=self.owner, notification_type="order_canceled")
            mock_send_notif.assert_called_once_with(
                user_id=self.owner.id,
                message=notification.message_content,
                title=notification.message_title,
                notif_type=notification.notification_type,
                target_url=notification.target_url
            )
            booking.refresh_from_db()
            self.assertTrue(Notification.objects.filter(receiver=self.owner, notification_type="order_canceled").exists())
            self.assertEqual(booking.status, 'canceled')
            self.assertRedirects(response, reverse('my_bookings'))
            self.assertEqual(notification.message_title, "הזמנה בוטלה!")
            self.assertIn(self.parking.name, notification.message_content)

    def test_booking_rejection_already_canceled(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
            status='canceled'
        )
        response = self.client.post(reverse('booking_rejection',args=[booking.id]),HTTP_REFERER=reverse('map_view'))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'הזמנה זו כבר בוטלה')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertRedirects(response,'/map/')

    def test_booking_rejection_canceling_time_passed(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=1),
            end_time=timezone.now() + timedelta(hours=4),
        )
        response = self.client.post(reverse('booking_rejection',args=[booking.id]),HTTP_REFERER=reverse('map_view'))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'זמן הביטול להזמנה זו חלף')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertRedirects(response,'/map/')

    def test_booking_rejection_get(self):
        self.client.force_login(self.owner)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
        )
        response = self.client.get(reverse('booking_rejection',args=[booking.id]))
        self.assertEqual(response.status_code,200)
        self.assertTemplateUsed(response,'parking/reject_booking.html')
        self.assertEqual(response.context['booking'], booking)

    # logout_view tests
    def test_logout_view_works(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('logout_view'))
        self.assertRedirects(response,reverse('map_view'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_view_requires_login(self):
        self.client.logout()
        response = self.client.post(reverse('logout_view'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, '/map/')

    def test_logout_view_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logout_view'))
        self.assertEqual(response.status_code, 405)

    # profile_view tests
    def test_profile_view_works(self):
        self.client.force_login(self.user)
        form_data = {
            'first_name': 'test',
            'last_name': 'test',
            'email': 'test@example.com'
        }
        response = self.client.post(reverse('profile'), data=form_data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'הפרופיל שלך עודכן בהצלחה!')
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertRedirects(response,reverse('profile'))

    # report_parking_space tests
    def test_report_parking_space_works(self):
        self.client.force_login(self.user)
        form_data = {
            'message_title': 'test',
            'reason': 'fake'
        }
        response = self.client.post(reverse('report_parking_space',args=[self.parking.id]),data=form_data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'הדיווח נשלח בהצלחה. אנו נבדוק את העניין בהקדם האפשרי.')
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertRedirects(response,reverse('map_view'))

    def test_report_parking_space_self_report(self):
        self.client.force_login(self.owner)
        form_data = {
            'message_title': 'test',
            'reason': 'fake'
        }
        response = self.client.post(reverse('report_parking_space',args=[self.parking.id]),data=form_data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'אינך יכול לדווח על חנייה שבבעלותך.')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertRedirects(response,reverse('map_view'))

    def test_report_parking_space_inaccurate_info(self):
        self.client.force_login(self.user)
        form_data = {
            'message_title': 'test',
            'reason': 'inaccurate_info'
        }
        with patch('parking.views.send_user_notification') as mock_send_notif:
            response = self.client.post(reverse('report_parking_space',args=[self.parking.id]),data=form_data)
            notification = Notification.objects.get(receiver=self.owner, notification_type="report")
            mock_send_notif.assert_called_once_with(
                user_id=self.owner.id,
                message=notification.message_content,
                title=notification.message_title,
                notif_type=notification.notification_type,
                target_url=notification.target_url
            )
            self.assertTrue(Notification.objects.filter(receiver=self.owner, notification_type="report").exists())
            messages = list(get_messages(response.wsgi_request))
            self.assertEqual(len(messages), 1)
            self.assertEqual(str(messages[0]), 'הדיווח נשלח בהצלחה. אנו נבדוק את העניין בהקדם האפשרי.')
            self.assertEqual(messages[0].level_tag, 'success')
            self.assertRedirects(response, reverse('map_view'))

    def test_report_parking_space_get(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('report_parking_space', args=[self.parking.id]))
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['parking'],self.parking)
        self.assertIsInstance(response.context['form'], ReportForm)
        self.assertTemplateUsed(response,'parking/report_parking_space.html')

    # rate_booking tests
    def test_rate_booking_works(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
            status='completed'
        )
        booking.save()
        owner_profile, _ = Profile.objects.get_or_create(user=self.user)
        owner_profile.phone_number = "0501234567"
        owner_profile.license_plate = "1234567"
        form_data = {
            'rating': 5,
            'rating_comment': 'rating test'
        }
        response = self.client.post(reverse('rate_booking',args=[booking.id]),data=form_data)
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'הדירוג נשמר בהצלחה!')
        self.assertEqual(messages[0].level_tag, 'success')
        self.assertRedirects(response, reverse('my_bookings'))
        booking.refresh_from_db()
        self.assertEqual(booking.rating, 5)
        self.assertEqual(booking.rating_comment, 'rating test')

    def test_rate_booking_not_completed(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
            status='pending'
        )
        booking.save()
        response = self.client.post(reverse('rate_booking',args=[booking.id]))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'אפשר לדרג רק הזמנה שהסתיימה.')
        self.assertEqual(messages[0].level_tag, 'error')
        self.assertRedirects(response, reverse('my_bookings'))

    def test_rate_booking_already_rated(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() + timedelta(hours=3),
            end_time=timezone.now() + timedelta(hours=4),
            status='completed',
            rating=4
        )
        booking.save()
        response = self.client.post(reverse('rate_booking', args=[booking.id]))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), 'כבר דירגת הזמנה זו.')
        self.assertEqual(messages[0].level_tag, 'info')
        self.assertRedirects(response, reverse('my_bookings'))

    def test_rate_booking_get(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() - timedelta(hours=5),
            end_time=timezone.now() - timedelta(hours=4),
            status='completed'
        )
        booking.save()
        response = self.client.get(reverse('rate_booking', args=[booking.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['booking'].id, booking.id)
        self.assertIsInstance(response.context['form'], BookingRatingForm)
        self.assertIsNone(response.context['next_url'])
        self.assertTemplateUsed(response,'parking/rate_booking.html')

    def test_rate_booking_invalid_form(self):
        self.client.force_login(self.user)
        booking = Booking.objects.create(
            buyer=self.user,
            parking_space=self.parking,
            start_time=timezone.now() - timedelta(hours=5),
            end_time=timezone.now() - timedelta(hours=4),
            status='completed'
        )
        invalid_data = {
            'rating': 99,
            'rating_comment': 'bad test'
        }

        response = self.client.post(reverse('rate_booking', args=[booking.id]), data=invalid_data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['form'].is_valid())

    # my_notifications tests
    def test_my_notifications_works(self):
        self.client.force_login(self.user)
        notfication = Notification.objects.create(
            receiver=self.user,
            message_content='Test Message',
            message_title='Test Title',
            notification_type='new_booking',
            target_url='/map/'
        )
        response = self.client.get(reverse('my_notifications'))
        self.assertEqual(response.status_code,200)
        self.assertIn(notfication, response.context['notifications'])
        self.assertTemplateUsed(response,'parking/notifications.html')

    # delete_notification tests
    def test_delete_notification_works(self):
        self.client.force_login(self.user)
        notfication = Notification.objects.create(
            receiver=self.user,
            message_content='Test Message',
            message_title='Test Title',
            notification_type='new_booking',
            target_url='/map/'
        )
        self.assertTrue(Notification.objects.filter(id=notfication.id).exists())
        response = self.client.post(reverse('delete_notification',args=[notfication.id]))
        self.assertFalse(Notification.objects.filter(id=notfication.id).exists())
        self.assertRedirects(response,reverse('my_notifications'))
