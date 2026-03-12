from django import forms
import datetime

from django.contrib.auth.models import User
from django.utils import timezone

from parking.models import Booking, ParkingSpace, Profile


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
        fields = ['name', 'city', 'address', 'price_per_hour', 'instructions', 'is_active' , 'available_from','available_to', 'available_sun', 'available_mon', 'available_tue', 'available_wed', 'available_thu', 'available_fri', 'available_sat','start_date', 'end_date']
        widgets = {
            'instructions': forms.Textarea(attrs={'rows': 3,'class': 'form-control'}),
            'available_from': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'available_to': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date','class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date','class': 'form-control'}),
            'lat': forms.HiddenInput(),
            'lon': forms.HiddenInput(),
        }

class BookingStatusForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField(required=True,label='אימייל')

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