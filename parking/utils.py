from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_user_notification(user_id, message, title="התראה"):

    channel_layer = get_channel_layer()
    group_name = f'user_{user_id}'

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'send_notification',
            'message': message,
            'title': title,
        }
    )