import json
from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer

class NotificationConsumer(WebsocketConsumer):
    def connect(self):
        self.user = self.scope['user']

        if self.user.is_authenticated:
            self.group_name = f'user_{self.user.id}'

            async_to_sync(self.channel_layer.group_add)(
                self.group_name,
                self.channel_name,
            )

            self.accept()
            print("WebSocket Connected!")
        else:
            self.close()
    def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            async_to_sync(self.channel_layer.group_discard)(
                self.group_name,
                self.channel_name,
            )
        print("WebSocket Disconnected...")

    def send_notification(self, event):
        message = event['message']
        title = event.get('title', 'התראה')
        notif_type = event.get('notif_type', 'info')
        target_url = event.get('target_url', '#')

        self.send(text_data=json.dumps({
            'message': message,
            'title': title,
            'type': notif_type,
            'url': target_url
        }))