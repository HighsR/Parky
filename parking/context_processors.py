from .models import Notification


def count_unread_notifications(request):
    if request.user.is_authenticated:
        return {'unread_count': Notification.objects.filter(receiver=request.user,is_read=False).count()}
    return {'unread_count': 0}