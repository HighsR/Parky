from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Avg
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.utils import timezone
from .models import ParkingSpace, Booking, Profile, Report
from .forms import BookingForm, ParkingSpaceForm, UserUpdateForm, ProfileUpdateForm, ReportForm, BookingRatingForm


def map_view(request):
    parkings = ParkingSpace.objects.filter(is_active=True, lat__isnull=False, lon__isnull=False).annotate(avg_rating=Avg('bookings__rating'))
    print(f"Found {len(parkings)} active parking spaces with coordinates.")
    return render(request, 'parking/map.html', {'parkings': parkings})

def mark_completed_bookings(bookings=None):
    if bookings is None:
         bookings = Booking.objects.all()
    return bookings.filter(status__in=['pending','approved'],end_time__lt=timezone.now()).update(status='completed')

@login_required
def book_parking(request, parking_id):
    parking_space = get_object_or_404(ParkingSpace, id=parking_id)
    profile,created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form=BookingForm(request.POST)
        if not profile.phone_number:
            messages.error(request,'בשביל לבצע הזמנה, עליך להוסיף מספר טלפון בפרופיל שלך.')
            return redirect('profile')
        if not profile.license_plate:
            messages.error(request, 'בשביל לבצע בזמנה, עליך להוסיף מספר רכב בפרופיל שלך.')
            return redirect('profile')
        if form.is_valid():
            booking=form.save(commit=False)
            booking.buyer=request.user
            booking.parking_space=parking_space

            try:
                booking.clean()
                booking.save()
                messages.success(request, 'החנייה הוזמנה בהצלחה!')
                return render(request, 'parking/booking_success.html', {'booking': booking})
            except ValidationError as e:
                form.add_error(None, e)
    else:
        form=BookingForm()

    return render(request, 'parking/book_parking.html', {'form': form, 'parking_space': parking_space})

@login_required
def my_bookings(request):
    bookings=Booking.objects.filter(buyer=request.user).order_by('-start_time')
    mark_completed_bookings(bookings)
    user_bookings = bookings.order_by('-start_time')

    return render(request, 'parking/my_bookings.html', {'bookings': user_bookings})

def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('map_view')
    else:
        form = UserCreationForm()

    return render(request, 'registration/register.html', {'form': form})

@login_required
def add_parking_space(request):
    if request.method == 'POST':
        form = ParkingSpaceForm(request.POST)

        if form.is_valid():
            parking_space = form.save(commit=False)
            parking_space.owner = request.user
            parking_space.is_active = True
            parking_space.save()
            if not parking_space.lat or not parking_space.lon:
                parking_space.delete()
                form.add_error(None, "לא הצלחנו למצוא את המיקום במפה. אנא דייק את הכתובת או סמן ידנית על המפה.")
            else:
                return redirect('parking_added_success')

    else:
        form = ParkingSpaceForm()

    return render(request, 'parking/add_parking_space.html', {'form': form})

@login_required
def my_listings(request):
    user_listings = ParkingSpace.objects.filter(owner=request.user).annotate(avg_rating=Avg('bookings__rating'))

    for p in user_listings:
        print(f"Parking: {p.address}, Avg Rating: {p.avg_rating}")

    return render(request, 'parking/my_listings.html', {'parkings': user_listings})

@login_required
def edit_parking_space(request, parking_id):
    parking_space = get_object_or_404(ParkingSpace, id=parking_id, owner=request.user)

    if request.method == 'POST':
        form = ParkingSpaceForm(request.POST, instance=parking_space)

        if form.is_valid():
            parking_space = form.save(commit=False)
            parking_space.save()
            return redirect('my_listings')
    else:
        form = ParkingSpaceForm(instance=parking_space)

    return render(request, 'parking/add_parking_space.html', {'form': form, 'edit_mode' : True, 'parking_space': parking_space})

@login_required
def delete_parking_space(request, parking_id):
    parking_space = get_object_or_404(ParkingSpace, id=parking_id, owner=request.user)

    if request.method == 'POST':
        parking_space.delete()
        return redirect('my_listings')

    return render(request, 'parking/delete_parking_space.html', {'parking_space': parking_space})

@login_required
def manage_seller_bookings(request):
    user_listings = ParkingSpace.objects.filter(owner=request.user, is_active=True)
    seller_orders = Booking.objects.filter(parking_space__in=user_listings)
    mark_completed_bookings(seller_orders)
    bookings = seller_orders.order_by('-start_time')
    return render(request, 'parking/manage_bookings.html', {'bookings': bookings })

@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, parking_space__owner=request.user)

    if request.method == 'POST':
        booking.status = 'approved'
        booking.save()
        messages.success(request, 'הזמנה אושרה!')
        return redirect('manage_seller_bookings')

    return render(request, 'parking/accept_booking.html', {'booking': booking})

@login_required
def booking_rejection(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, parking_space__owner=request.user)

    if request.method == 'POST':
        booking.status = 'canceled'
        booking.save()
        messages.success(request, 'הזמנה בוטלה!')
        return redirect('manage_seller_bookings')

    return render(request, 'parking/reject_booking.html', {'booking': booking})

@login_required
def logout_view(request):
    logout(request)

    messages.success(request,'התנתקת בהצלחה!')

    return redirect('map_view')

@login_required
def profile_view(request):
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(request.POST, instance=profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request,'הפרופיל שלך עודכן בהצלחה!')
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    return render(request, 'parking/profile.html', {'user_form': user_form, 'profile_form': profile_form})

@login_required
def report_parking_space(request,parking_id):
    parking = get_object_or_404(ParkingSpace, id=parking_id)

    if request.method == 'POST':
        form = ReportForm(request.POST)

        if form.is_valid():
            report = form.save(commit=False)

            report.parking_space = parking
            report.reporter = request.user

            report.save()

            messages.success(request, 'הדיווח נשלח בהצלחה. אנו נבדוק את העניין בהקדם האפשרי.')
            return redirect('map_view')
    else:
        form = ReportForm()

    context = {'parking': parking, 'form': form}

    return render(request, 'parking/report_parking_space.html', context)
@login_required
def rate_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, buyer=request.user)
    next_url = request.POST.get('next') or request.GET.get('next')

    if booking.status != 'completed':
        messages.error(request,'אפשר לדרג רק הזמנה שהסתיימה.')
        return redirect(next_url or 'my_bookings')

    if booking.rating is not None:
        messages.info(request, "כבר דירגת הזמנה זו.")
        return redirect(next_url or 'my_bookings')

    if request.method == 'POST':
        form = BookingRatingForm(request.POST, instance=booking)
        if form.is_valid():
            rating=form.save(commit=False)
            rating.rated_at = timezone.now()
            rating.save(update_fields=['rating','rating_comment','rated_at'])

            owner = booking.parking_space.owner
            avg = Booking.objects.filter(parking_space__owner=owner,rating__isnull=False ).aggregate(Avg('rating'))['rating__avg']

            owner_profile, created = Profile.objects.get_or_create(user=owner)
            owner_profile.user_rating = avg or 0
            owner_profile.save(update_fields=['user_rating'])

            messages.success(request,'הדירוג נשמר בהצלחה!')
            return redirect(next_url or 'my_bookings')
        else:
            print(form.errors)
    else:
        form = BookingRatingForm(instance=booking)

    return render(request, 'parking/rate_booking.html', {'booking': booking, 'form': form,'next_url': next_url})