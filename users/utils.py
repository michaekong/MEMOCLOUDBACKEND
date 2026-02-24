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
# users/audit_utils.py
# users/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import mail_admins
from django.conf import settings
from .models import AuditLog


@receiver(post_save, sender=AuditLog)
def alert_critical_action(sender, instance, created, **kwargs):
    """
    Envoie une alerte email pour toute action CRITICAL.
    """
    if not created:
        return
    
    if instance.severity != AuditLog.Severity.CRITICAL:
        return
    
    # Construire le message
    subject = f'🚨 [CRITIQUE] {instance.get_action_display()} - {instance.user_email or "Système"}'
    
    message = f"""
ACTION CRITIQUE DÉTECTÉE
========================

Action      : {instance.get_action_display()}
Sévérité    : {instance.get_severity_display()}
Date        : {instance.created_at}
Utilisateur : {instance.user_email or 'Système'} (Rôle: {instance.user_role or 'N/A'})
Université  : {instance.university.nom if instance.university else 'N/A'}
IP          : {instance.ip_address or 'N/A'}

Cible       : [{instance.target_type}] {instance.target_repr}

Description :
{instance.description or 'Aucune description'}

Données avant :
{instance.previous_data or 'N/A'}

Données après :
{instance.new_data or 'N/A'}

---
Ce message est automatique. Consultez l'admin Django pour plus de détails.
{settings.ADMIN_URL if hasattr(settings, 'ADMIN_URL') else '/admin/'}
"""
    
    # Envoyer aux admins
    try:
        mail_admins(
            subject=subject,
            message=message,
            fail_silently=True
        )
    except Exception as e:
        # Ne pas bloquer si l'email échoue
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Échec envoi alerte critique: {e}")
# users/audit_utils.py
import json
from functools import wraps
from django.db import models
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from .models import AuditLog, CustomUser
from universites.models import Universite


def get_client_ip(request: HttpRequest) -> str:
    """Récupère l'IP client de manière sécurisée."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def serialize_instance(instance: models.Model) -> dict:
    """Sérialise une instance de modèle en dictionnaire."""
    if not isinstance(instance, models.Model):
        return {'value': str(instance)}
    
    data = {}
    for field in instance._meta.fields:
        try:
            value = getattr(instance, field.name)
            
            if field.name in ['password', 'code', 'token']:
                data[field.name] = '[MASQUÉ]'
                continue
            
            if hasattr(value, 'pk'):
                data[field.name] = {
                    'id': value.pk,
                    'repr': str(value)[:100]
                }
            elif hasattr(value, 'url'):
                data[field.name] = str(value)
            else:
                data[field.name] = str(value)[:500] if value is not None else ''
                
        except Exception as e:
            data[field.name] = f'[Erreur: {str(e)}]'
    
    return data


# users/utils.py
def create_audit_log(
    action,
    severity,
    user=None,  # Instance de CustomUser
    university=None,
    target=None,
    target_type=None,
    target_id=None,
    target_repr=None,
    previous_data=None,
    new_data=None,
    description=None,
    request=None,
    **extra_fields
):
    """Crée un log d'audit sans ForeignKey problématique."""
    log_data = {
        'action': action,
        'severity': severity,
        'description': description or '',
    }
    
    # Stocker les infos utilisateur en dur, pas de FK
    if user:
        log_data['user_id'] = user.id
        log_data['user_email'] = user.email
        log_data['user_role'] = getattr(user, 'type', 'unknown')
    
    if university:
        log_data['university'] = university
    
    if target:
        log_data['target_type'] = target_type or target.__class__.__name__
        log_data['target_id'] = str(getattr(target, 'pk', target_id) or '')
        log_data['target_repr'] = target_repr or str(target)[:500]
    else:
        log_data['target_type'] = target_type or ''
        log_data['target_id'] = str(target_id or '')
        log_data['target_repr'] = target_repr or ''
    
    if previous_data:
        log_data['previous_data'] = previous_data
    if new_data:
        log_data['new_data'] = new_data
    
    if request:
        log_data['ip_address'] = get_client_ip(request)
        log_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')[:500]
        log_data['request_path'] = request.path
        log_data['request_method'] = request.method
    
    log_data.update(extra_fields)
    
    return AuditLog.objects.create(**log_data)

class AuditMixin:
    """
    Mixin pour les vues API avec récupération automatique de l'université
    via le slug dans l'URL (univ_slug).
    """
    audit_action: AuditLog.ActionType = None
    audit_severity: AuditLog.Severity = AuditLog.Severity.MEDIUM
    audit_target_type: str = None
    
    # Nom du paramètre dans l'URL contenant le slug de l'université
    univ_slug_param: str = 'univ_slug'
    
    def get_audit_user(self):
        """Retourne l'utilisateur connecté."""
        request = getattr(self, 'request', None)
        if request and request.user.is_authenticated:
            return request.user
        return None
    
    def get_univ_slug_from_url(self):
        """
        Récupère le slug de l'université depuis les kwargs de l'URL.
        Fonctionne avec votre pattern d'URL : /<slug:univ_slug>/...
        """
        # Depuis les attributs de la vue (set par Django lors du dispatch)
        kwargs = getattr(self, 'kwargs', {})
        return kwargs.get(self.univ_slug_param)
    
    def get_audit_university(self):
        """
        Récupère l'objet Université à partir du slug dans l'URL.
        Met en cache pour éviter les requêtes multiples.
        """
        if not hasattr(self, '_cached_university'):
            slug = self.get_univ_slug_from_url()
            if slug:
                try:
                    self._cached_university = get_object_or_404(Universite, slug=slug)
                except Exception:
                    self._cached_university = None
            else:
                self._cached_university = None
        return self._cached_university
    
    def get_audit_target(self):
        """À surcharger pour retourner la cible de l'action."""
        if hasattr(self, 'get_object'):
            try:
                return self.get_object()
            except Exception:
                pass
        return None
    
    def log_action(
        self,
        action: AuditLog.ActionType = None,
        severity: AuditLog.Severity = None,
        target=None,
        previous_data: dict = None,
        new_data: dict = None,
        description: str = None,
        **extra
    ) -> AuditLog:
        """Crée un log d'audit avec l'université automatique."""
        request = getattr(self, 'request', None)
        
        # Construction de la description avec l'université
        university = self.get_audit_university()
        auto_description = description or ''
        if university and not auto_description.startswith(university.nom):
            auto_description = f"[{university.nom}] {auto_description}"
        
        return create_audit_log(
            action=action or self.audit_action,
            severity=severity or self.audit_severity,
            user=self.get_audit_user(),
            university=university,
            target=target or self.get_audit_target(),
            target_type=self.audit_target_type,
            previous_data=previous_data,
            new_data=new_data,
            description=auto_description,
            request=request,
            **extra
        )
    
    def perform_create(self, serializer):
        """Création avec logging automatique."""
        instance = serializer.save()
        
        if self.audit_action:
            self.log_action(
                new_data=serialize_instance(instance),
                description=f"Création: {instance}"
            )
        return instance
    
    def perform_update(self, serializer):
        """Modification avec logging automatique."""
        old_instance = self.get_object()
        previous_data = serialize_instance(old_instance)
        
        instance = serializer.save()
        
        if self.audit_action:
            self.log_action(
                target=instance,
                previous_data=previous_data,
                new_data=serialize_instance(instance),
                description=f"Modification: {instance}"
            )
        return instance
    
    def perform_destroy(self, instance):
        """Suppression avec logging automatique."""
        previous_data = serialize_instance(instance)
        
        if self.audit_action:
            self.log_action(
                target=instance,
                previous_data=previous_data,
                description=f"Suppression: {instance}"
            )
        
        if hasattr(super(), 'perform_destroy'):
            super().perform_destroy(instance)
        else:
            instance.delete()


# Décorateur avec support automatique du slug
def audit_log(
    action: AuditLog.ActionType,
    severity: AuditLog.Severity = AuditLog.Severity.MEDIUM,
    get_target=None,
    with_university=True
):
    """
    Décorateur pour logger une action avec récupération auto de l'université.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Récupération auto de l'université depuis l'URL
            university = None
            if with_university and 'univ_slug' in kwargs:
                try:
                    university = Universite.objects.get(slug=kwargs['univ_slug'])
                except Universite.DoesNotExist:
                    pass
            
            # Récupération de la cible si fournie
            target = None
            if get_target:
                try:
                    target = get_target(self, request, *args, **kwargs)
                except Exception:
                    pass
            
            # Exécution de la vue
            response = func(self, request, *args, **kwargs)
            
            # Logging si succès
            if 200 <= response.status_code < 400:
                user = request.user if request.user.is_authenticated else None
                
                desc = f"{action} exécuté via {func.__name__}"
                if university:
                    desc = f"[{university.nom}] {desc}"
                
                create_audit_log(
                    action=action,
                    severity=severity,
                    user=user,
                    university=university,
                    target=target,
                    request=request,
                    description=desc
                )
            
            return response
        return wrapper
    return decorator