from django.db import models
from django.contrib.auth.models import User
from geopy.geocoders import Nominatim
from django.core.exceptions import ValidationError
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


class ParkingSpace(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    price_per_hour=models.DecimalField(max_digits=10, decimal_places=2)
    instructions = models.TextField(blank=True, null=True, help_text="הוראות מיוחדות למשתמשים (למשל: מיקום מדויק, דרכי גישה, וכו')")
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    legal_declaration = models.BooleanField(default=False, verbose_name="אני מאשר שהחנייה בבעלותי או שיש לי אישור חוקי להשכיר אותה.", help_text="חובה לאשר את ההצהרה המשפטית כדי להוסיף חניה למערכת.")

    start_date = models.DateField(null=True, blank=True, help_text="תאריך התחלה לזמינות החניה")
    end_date = models.DateField(null=True, blank=True, help_text="תאריך סיום לזמינות החניה")
    available_from=models.TimeField(null=True, blank=True, help_text="שעת התחלה לזמינות החניה בכל יום")
    available_to=models.TimeField(null=True, blank=True, help_text="שעת סיום לזמינות החניה בכל יום")
    available_sun = models.BooleanField(default=True, verbose_name="א'")
    available_mon = models.BooleanField(default=True, verbose_name="ב'")
    available_tue = models.BooleanField(default=True, verbose_name="ג'")
    available_wed = models.BooleanField(default=True, verbose_name="ד'")
    available_thu = models.BooleanField(default=True, verbose_name="ה'")
    available_fri = models.BooleanField(default=True, verbose_name="ו'")
    available_sat = models.BooleanField(default=True, verbose_name="ש'")

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.address and (self.lat is None or self.lon is None):
            try:
                geolocator = Nominatim(user_agent="Parky_App_Project" , timeout=10)
                address_string = f"{self.address}, {self.city}, Israel"
                location = geolocator.geocode(address_string)
                print(f"Geocoding address: {address_string} -> {location}")
                if location:
                    self.lat = location.latitude
                    self.lon = location.longitude
                else:
                    raise ValidationError(f"הכתובת '{address_string}' לא נמצאה במפה. אנא הזן כתובת מדויקת יותר.")
            except Exception as e:
                raise ValidationError(f"שגיאה בניסיון לאתר את הכתובת במפה: {e}")

        super().save(*args, **kwargs)
    def clean(self):
        super().clean()
        if not self.legal_declaration:
            raise ValidationError("חובה לאשר הצהרה חוקית")

        if self.price_per_hour and self.price_per_hour < 0:
            raise ValidationError("המחיר לא יכול להיות שלילי")

        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError("תאריך הסיום לא יכול להיות מוקדם מתאריך ההתחלה.")
        if self.available_from and self.available_to:
            if self.available_from > self.available_to:
                raise ValidationError("זמן סיום לא יכול להיות מוקדם מזמן ההתחלה.")

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
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_comment = models.TextField(null=True, blank=True)
    rated_at = models.DateTimeField(null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    status = models.CharField(max_length=20,choices=STATUS_CHOICES, default='pending')


    def clean(self):
        super().clean()
        if not self.start_time or not self.end_time:
            raise ValidationError("זמני התחלה וסיום הם שדות חובה.")

        if self.start_time >= self.end_time:
            raise ValidationError("זמן ההתחלה חייב להיות לפני זמן הסיום.")
        try:
            if self.parking_space and self.buyer:

                if not self.pk:
                    if timezone.now() > self.end_time or timezone.now() > self.start_time:
                        raise ValidationError("לא ניתן להזמין חניה לזמן שעבר.")

                    parking=self.parking_space

                    if parking.start_date and self.start_time.date() < parking.start_date:
                        raise ValidationError(f"החניה זמינה החל מ-{parking.start_date}")

                    if parking.end_date and self.end_time.date() > parking.end_date:
                        raise ValidationError(f"החניה זמינה עד {parking.end_date}")

                    if parking.available_from and parking.available_to:
                        if self.start_time.time() < parking.available_from or self.end_time.time() > parking.available_to:
                            raise ValidationError(f'החנייה זמינה רק בין השעות {parking.available_from.strftime("%H:%M")} ל-{parking.available_to.strftime("%H:%M")}.')

                    available_days = {
                        0: parking.available_mon,
                        1: parking.available_tue,
                        2: parking.available_wed,
                        3: parking.available_thu,
                        4: parking.available_fri,
                        5: parking.available_sat,
                        6: parking.available_sun,
                    }

                    if not available_days[self.start_time.weekday()] or not available_days[self.end_time.weekday()]:
                        raise ValidationError(f"החניה לא זמינה בימי {self.start_time.strftime('%A')}")

                if self.parking_space.bookings.filter(status__in=['pending', 'approved'], start_time__lt=self.end_time,
                                                      end_time__gt=self.start_time).exclude(id=self.id).exists():
                    raise ValidationError(" החניה כבר הוזמנה לתקופה זו. אנא בחר זמן אחר.")

        except (ParkingSpace.DoesNotExist, User.DoesNotExist):
            pass
    def __str__(self):
        return f"Booking by {self.buyer.username} for {self.parking_space.name} from {self.start_time} to {self.end_time} - Status: {self.status}"

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    phone_number = PhoneNumberField(unique=True, blank=True , null=True)

    license_plate = models.CharField(max_length=8 , unique=True, blank=True , null=True)

    user_rating = models.FloatField(default=0)

    def __str__(self):
        return f"{self.user.username} Profile"

class Report(models.Model):
    REASON_CHOICES = [
        ('fake', 'חניה לא קיימת'),
        ('not_owner','החניה לא בבעלות המפרסם'),
        ('inaccurate_info','מידע לא מדויק'),
        ('scam', 'חשד להונאה'),
        ('other', 'אחר'),
    ]
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.CASCADE, related_name='reports')
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='filed_reports', verbose_name='מדווח')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES,verbose_name='סיבת הדיווח')
    description = models.TextField(blank=True, null=True,verbose_name='תיאור נוסף (אופציונלי)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='נוצר ב')
    is_resolved = models.BooleanField(default=False,verbose_name='טופל')

    def __str__(self):
        return f"דיווח על חניה {self.parking_space.id} מאת {self.reporter.username}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_booking', 'הזמנה חדשה'),
        ('report', 'דיווח על חניה'),
        ('order_canceled', 'הזמנה בוטלה'),
        ('order_confirmed', 'הזמנה אושרה'),
    ]
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name='מקבל')
    message_title = models.CharField(max_length=100, verbose_name='כותרת')
    message_content = models.TextField(verbose_name='תוכן ההודעה')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='תאריך יצירה')
    is_read = models.BooleanField(default=False, verbose_name='נקרא')
    notification_type = models.CharField(max_length=100, choices=TYPE_CHOICES, verbose_name='סוג התראה')
    target_url = models.URLField(max_length=200, blank=False, verbose_name='קישור ליעד')

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.message_title} - {self.receiver.username}"
