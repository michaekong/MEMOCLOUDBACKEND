import os
import django
from channels.routing import ProtocolTypeRouter
from channels.auth import AuthMiddlewareStack
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()  # Important to call before creating the application

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # Remove the websocket entry if not needed
})

# If you need to handle WebSocket connections later, add them here.