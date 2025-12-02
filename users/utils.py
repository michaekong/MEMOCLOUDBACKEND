from mailersend import MailerSendClient, EmailBuilder
from django.conf import settings
from django.template.loader import render_to_string
from decouple import config

def send_verification_email(to_email: str, verification_url: str):
    api = config('MAILERSEND_API_KEY')
    # Initialiser le client MailerSend avec la clé API
    ms = MailerSendClient(api_key=api)
    html = render_to_string('emails/verify_email.html', context={'verify_url': verification_url})

    # Construire l'email
    email = (EmailBuilder()
             .from_email(settings.DEFAULT_FROM_EMAIL, "test-r83ql3pk69xgzw1j.mlsender.net")
             .to_many([{"email": to_email, "name": to_email.split("@")[0]}])
             .subject("Vérification de votre email")
             .html(html)
             .text(f"Bonjour, merci de vous être inscrit. Vérifiez votre email ici : {verification_url}")
             .build())

    # Envoyer l'email
    response = ms.emails.send(email)
    return response
