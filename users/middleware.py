# users/middleware.py
import logging
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import AuditLog
from .utils import get_client_ip

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditMiddleware:
    """
    Middleware pour logger automatiquement :
    - Les échecs de connexion
    - Les connexions réussies des admins
    - Les erreurs 403 sur actions sensibles
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Traitement avant la vue
        self.process_request(request)
        
        response = self.get_response(request)
        
        # Traitement après la vue
        self.process_response(request, response)
        
        return response
    
    def process_request(self, request):
        """Capture les infos de la requête."""
        request.audit_start_time = timezone.now()
        request.audit_sensitive_path = self._is_sensitive_path(request.path)
    
    def process_response(self, request, response):
        """Log les actions importantes après la réponse."""
        
        # 1. Log les échecs de connexion (401/403 sur /login/)
        if response.status_code in [401, 403] and '/login' in request.path:
            self._log_login_failed(request, response)
        
        # 2. Log les connexions réussies d'admins (POST /login/ → 200 avec token)
        if request.method == 'POST' and '/login' in request.path and response.status_code == 200:
            if hasattr(response, 'data') and 'user' in response.data:
                user_data = response.data.get('user', {})
                if user_data.get('type') in ['admin', 'superadmin', 'bigboss']:
                    self._log_admin_login(request, response, user_data)
        
        # 3. Log les erreurs 403 sur chemins sensibles
        if response.status_code == 403 and request.audit_sensitive_path:
            self._log_forbidden_access(request, response)
        
        return response
    
    def _is_sensitive_path(self, path: str) -> bool:
        """Détermine si un chemin est sensible et mérite d'être loggué en cas de 403."""
        sensitive_patterns = [
            '/admin/',
            '/suppression-totale',
            '/bulk-delete',
            '/role',
            '/moderer',
            '/marquer-traite',
        ]
        return any(pattern in path for pattern in sensitive_patterns)
    
    def _log_login_failed(self, request, response):
        """Log un échec de connexion."""
        try:
            email = request.data.get('email', 'unknown') if hasattr(request, 'data') else 'unknown'
            
            AuditLog.objects.create(
                action=AuditLog.ActionType.LOGIN_FAILED,
                severity=AuditLog.Severity.MEDIUM,
                user_email=email,
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                request_path=request.path,
                request_method=request.method,
                description=f"Tentative de connexion échouée pour {email}",
                new_data={
                    'status_code': response.status_code,
                    'error_detail': getattr(response, 'data', {}).get('detail', 'Unknown error')
                }
            )
        except Exception as e:
            logger.error(f"Erreur logging login failed: {e}")
    
    def _log_admin_login(self, request, response, user_data):
        """Log la connexion d'un administrateur."""
        try:
            user_id = user_data.get('id')
            user = User.objects.get(id=user_id) if user_id else None
            
            AuditLog.objects.create(
                action=AuditLog.ActionType.LOGIN,
                severity=AuditLog.Severity.LOW,
                user=user,
                user_email=user.email if user else user_data.get('email'),
                user_role=user_data.get('type'),
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                request_path=request.path,
                request_method=request.method,
                description=f"Connexion administrateur ({user_data.get('type')}) : {user_data.get('email')}"
            )
        except Exception as e:
            logger.error(f"Erreur logging admin login: {e}")
    
    def _log_forbidden_access(self, request, response):
        """Log un accès interdit sur chemin sensible."""
        try:
            user = request.user if request.user.is_authenticated else None
            
            AuditLog.objects.create(
                action=AuditLog.ActionType.LOGIN_FAILED,  # Ou créer une action dédiée
                severity=AuditLog.Severity.HIGH,
                user=user,
                user_email=user.email if user else 'Anonymous',
                user_role=getattr(user, 'type', 'anonymous') if user else 'anonymous',
                ip_address=get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
                request_path=request.path,
                request_method=request.method,
                description=f"Accès interdit (403) sur ressource sensible par {user.email if user else 'Anonymous'}"
            )
        except Exception as e:
            logger.error(f"Erreur logging forbidden access: {e}")