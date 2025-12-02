from django.core import signing
from django.conf import settings
from datetime import timedelta

SALT = "users.email.verify"

def make_email_token(user_id, expires_in=60*60*24):
    payload = {"user_id": user_id}
    signed = signing.dumps(payload, salt=SALT)
    return signed

def verify_email_token(token):
    try:
        payload = signing.loads(token, salt=SALT, max_age=60*60*24)  # 24h default
        return payload.get("user_id")
    except Exception:
        return None
