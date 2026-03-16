from django import forms
import datetime
import requests

from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ValidationError
from parking.models import Booking, ParkingSpace, Profile, Report


class BookingForm(forms.ModelForm):
    booking_date = forms.DateField(label='תאריך חנייה',widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    start_hour = forms.TimeField(label='משעה',widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}))
    end_hour = forms.TimeField(label='עד שעה',widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}))

    class Meta:
        model = Booking
        fields = []
    def clean(self):
        cleaned_data = super().clean()
        booking_date = cleaned_data.get('booking_date')
        start_hour = cleaned_data.get('start_hour')
        end_hour = cleaned_data.get('end_hour')

        if booking_date and start_hour and end_hour:
            start_dt = datetime.datetime.combine(booking_date, start_hour)
            end_dt = datetime.datetime.combine(booking_date, end_hour)

            self.instance.start_time = timezone.make_aware(start_dt)
            self.instance.end_time = timezone.make_aware(end_dt)
        return cleaned_data

class ParkingSpaceForm(forms.ModelForm):
    class Meta:
        model = ParkingSpace
        fields = ['name', 'city', 'address', 'price_per_hour', 'instructions', 'is_active' ,'legal_declaration', 'available_from','available_to', 'available_sun', 'available_mon', 'available_tue', 'available_wed', 'available_thu', 'available_fri', 'available_sat','start_date', 'end_date']
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 3,'class': 'form-control'}),
            'available_from': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'available_to': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date','class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date','class': 'form-control'}),
            'lat': forms.HiddenInput(),
            'lon': forms.HiddenInput(),
        }
    def clean_legal_declaration(self):
        legal_declaration = self.cleaned_data.get('legal_declaration')
        if not legal_declaration:
            raise ValidationError('עליך לאשר את ההצהרה המשפטית כדי להוסיף חניה למערכת.')
        return legal_declaration

class BookingStatusForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        label='דוא"ל',
        error_messages={
            'invalid': 'אנא הזן כתובת מייל חוקית.',
            'unique': 'כתובת מייל זו כבר קיימת במערכת. אנא הזן כתובת מייל אחרת.',
            }
    )

    class Meta:
        model = User
        fields = ['first_name','last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone_number', 'license_plate']
        labels = {
            'phone_number': 'מספר טלפון',
            'license_plate': 'מספר רכב'
        }
        error_messages = {
            'phone_number': {
                'invalid': 'מספר טלפון לא חוקי. אנא הזן מספר טלפון תקין.',
                'unique': 'מספר טלפון זה כבר קיים במערכת. אנא הזן מספר טלפון אחר.',
            }

        }
    def clean_license_plate(self):
        plate = self.cleaned_data.get('license_plate')
        if not plate:
            return plate

        if self.instance and self.instance.license_plate == plate:
            return plate

        base_url='https://data.gov.il/api/3/action/datastore_search'
        params1={
            'resource_id': '053cea08-09bc-40ec-8f7a-156f0677aff3',
            'filters': f'{{"mispar_rechev": "{plate}"}}'
        }
        params2={
            'resource_id': '0866573c-40cd-4ca8-91d2-9dd2d7a492e5',
        'filters': f'{{"mispar_rechev": "{plate}"}}'
        }
        try:
            first_response=requests.get(base_url, params=params1,timeout=5)
        except requests.RequestException:
            raise ValidationError('אירעה שגיאה בעת אימות מספר הרכב. אנא נסה שוב מאוחר יותר.')


        if first_response.status_code == 200:
            first_data=first_response.json()
            first_records = first_data.get('result', {}).get('records', [])

            if len(first_records) != 0:
                return plate
        try:
            second_response = requests.get(base_url, params=params2,timeout=5)
        except requests.RequestException:
            raise ValidationError('אירעה שגיאה בעת אימות מספר הרכב. אנא נסה שוב מאוחר יותר.')

        if second_response.status_code == 200:
            second_data = second_response.json()
            second_records = second_data.get('result', {}).get('records', [])

            if len(second_records) != 0:
                return plate

        raise ValidationError('מספר רכב לא נמצא במאגר הרכב הישראלי. אנא בדוק את מספר הרכב ונסה שוב.')

class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ['reason' , 'description']
        widgets = {
            'reason': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'פרט קצת יותר על הבעיה...'}),
        }

class BookingRatingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['rating', 'rating_comment']
        widgets = {
            'rating': forms.NumberInput(attrs={"min": 1, "max": 5, "class": "form-control"}),
            'rating_comment': forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None and (rating < 1 or rating > 5):
            raise ValidationError('הדירוג חייב להיות בין 1 ל-5.')
        return rating