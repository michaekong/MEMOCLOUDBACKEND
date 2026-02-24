# users/audit_notifications.py
import logging
from django.conf import settings
from django.template.loader import render_to_string
from mailersend import MailerSendClient, EmailBuilder
from decouple import config

logger = logging.getLogger(__name__)


def get_mailer_client():
    """Initialise et retourne le client MailerSend."""
    api_key = config('MAILERSEND_API_KEY', default=None)
    if not api_key:
        logger.error("MAILERSEND_API_KEY non configuré")
        return None
    return MailerSendClient(api_key=api_key)


def get_university_admins_by_role(university):
    """
    Récupère les emails des admins de l'université via RoleUniversite.
    Retourne les utilisateurs avec rôle: admin, superadmin ou bigboss.
    """
    if not university:
        return []
    
    # Importer ici pour éviter les imports circulaires
    from universites.models import RoleUniversite
    
    # Récupérer les rôles admin de cette université
    admin_roles = RoleUniversite.objects.filter(
        universite=university,
        role__in=['admin', 'superadmin', 'bigboss']
    ).select_related('utilisateur')
    
    # Extraire les emails uniques
    admin_emails = []
    seen_emails = set()
    
    for role in admin_roles:
        user = role.utilisateur
        email = user.email
        if email and email not in seen_emails:
            admin_emails.append({
                "email": email,
                "name": f"{user.prenom} {user.nom}".strip() or email
            })
            seen_emails.add(email)
    
    logger.info(f"Trouvé {len(admin_emails)} admins pour {university.nom} "
                f"(roles: admin, superadmin, bigboss)")
    
    return admin_emails


def send_critical_alert_to_admins(audit_log):
    """
    Envoie une alerte email aux admins de l'université concernée
    pour les actions CRITICAL.
    """
    if audit_log.severity != audit_log.Severity.CRITICAL:
        return
    
    # Récupérer les admins via RoleUniversite
    admins = get_university_admins_by_role(audit_log.university)
    
    if not admins:
        logger.warning(f"Aucun admin (role admin/superadmin/bigboss) trouvé "
                      f"pour l'université {audit_log.university}")
        # Fallback: superadmins Django
        admins = get_fallback_admins()
        if not admins:
            return
    
    # Initialiser MailerSend
    ms = get_mailer_client()
    if not ms:
        logger.error("Impossible d'initialiser MailerSend")
        return
    
    # Construire le contenu
    html_content = render_to_string('emails/critical_audit_alert.html', {
        'audit_log': audit_log,
        'university': audit_log.university,
        'action_display': audit_log.get_action_display(),
        'severity_display': audit_log.get_severity_display(),
    })
    
    text_content = build_text_content(audit_log)
    
    try:
        # Construire l'email avec TOUS les admins en destinataires
        email_builder = (EmailBuilder()
            .from_email(settings.DEFAULT_FROM_EMAIL, "Système de Traçabilité")
            .subject(f'🚨 [CRITIQUE] {audit_log.get_action_display()} - '
                    f'{audit_log.university.nom if audit_log.university else "Système"}')
            .html(html_content)
            .text(text_content)
        )
        
        # Ajouter chaque admin individuellement (MailerSend format)
        for admin in admins:
            email_builder = email_builder.to(admin["email"], admin["name"])
        
        email = email_builder.build()
        
        # Envoyer
        response = ms.emails.send(email)
        logger.info(f"✅ Alerte critique envoyée à {len(admins)} admins "
                   f"({[a['email'] for a in admins]}) pour action {audit_log.action}")
        return response
        
    except Exception as e:
        logger.error(f"❌ Échec envoi alerte critique: {e}")
        return None


def build_text_content(audit_log):
    """Construit le contenu texte de l'alerte."""
    lines = [
        "🚨 ALERTE CRITIQUE",
        "=" * 50,
        f"Université: {audit_log.university.nom if audit_log.university else 'N/A'}",
        f"Action: {audit_log.get_action_display()}",
        f"Sévérité: {audit_log.get_severity_display()}",
        f"Date: {audit_log.created_at.strftime('%d/%m/%Y %H:%M:%S')}",
        f"Utilisateur: {audit_log.user_email or 'Système'} (rôle: {audit_log.user_role or 'N/A'})",
        f"IP: {audit_log.ip_address or 'N/A'}",
        "",
        f"Cible: [{audit_log.target_type}] {audit_log.target_repr}",
        "",
        "Description:",
        audit_log.description or "Aucune description",
    ]
    
    if audit_log.previous_data:
        lines.extend(["", "Données avant:", str(audit_log.previous_data)])
    
    if audit_log.new_data:
        lines.extend(["", "Données après:", str(audit_log.new_data)])
    
    lines.extend([
        "",
        "-" * 50,
        f"Consultez les logs: {getattr(settings, 'FRONTEND_URL', '')}/admin/audit-logs/{audit_log.id}/"
    ])
    
    return "\n".join(lines)


def get_fallback_admins():
    """
    Récupère les superadmins Django comme fallback.
    """
    from users.models import CustomUser
    
    superadmins = CustomUser.objects.filter(is_superuser=True)
    admins = []
    
    for user in superadmins:
        if user.email:
            admins.append({
                "email": user.email,
                "name": f"{user.prenom} {user.nom}".strip() or user.email
            })
    
    if admins:
        logger.info(f"Fallback: {len(admins)} superadmins Django trouvés")
    
    return admins


def get_admins_by_minimum_role(university, min_role='admin'):
    """
    Option: Récupérer les admins avec un rôle minimum spécifique.
    min_role peut être: 'admin', 'superadmin', 'bigboss'
    """
    from universites.models import RoleUniversite
    
    role_hierarchy = {
        'admin': ['admin', 'superadmin', 'bigboss'],
        'superadmin': ['superadmin', 'bigboss'],
        'bigboss': ['bigboss']
    }
    
    allowed_roles = role_hierarchy.get(min_role, ['admin', 'superadmin', 'bigboss'])
    
    roles = RoleUniversite.objects.filter(
        universite=university,
        role__in=allowed_roles
    ).select_related('utilisateur')
    
    admins = []
    seen = set()
    
    for role in roles:
        email = role.utilisateur.email
        if email and email not in seen:
            admins.append({
                "email": email,
                "name": f"{role.utilisateur.prenom} {role.utilisateur.nom}".strip() or email,
                "role": role.role  # Inclure le rôle pour info
            })
            seen.add(email)
    
    return admins


def notify_specific_role(audit_log, target_role='superadmin'):
    """
    Notifier uniquement un rôle spécifique (ex: uniquement les bigboss).
    """
    if not audit_log.university:
        return
    
    from universites.models import RoleUniversite
    
    roles = RoleUniversite.objects.filter(
        universite=audit_log.university,
        role=target_role
    ).select_related('utilisateur')
    
    recipients = []
    for role in roles:
        if role.utilisateur.email:
            recipients.append({
                "email": role.utilisateur.email,
                "name": f"{role.utilisateur.prenom} {role.utilisateur.nom}".strip()
            })
    
    if not recipients:
        logger.warning(f"Aucun utilisateur avec rôle '{target_role}' trouvé")
        return
    
    ms = get_mailer_client()
    if not ms:
        return
    
    try:
        email_builder = (EmailBuilder()
            .from_email(settings.DEFAULT_FROM_EMAIL, "Système de Traçabilité")
            .subject(f'🚨 [CRITIQUE-{target_role.upper()}] {audit_log.get_action_display()}')
            .html(f"<p>Alerte pour les {target_role}s uniquement</p>")
            .text(f"Alerte pour les {target_role}s")
        )
        
        for r in recipients:
            email_builder = email_builder.to(r["email"], r["name"])
        
        ms.emails.send(email_builder.build())
        logger.info(f"Notification {target_role} envoyée à {len(recipients)} personnes")
        
    except Exception as e:
        logger.error(f"Échec notification {target_role}: {e}")