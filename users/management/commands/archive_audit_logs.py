# users/management/commands/archive_audit_logs.py
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from users.models import AuditLog
import json
import os


class Command(BaseCommand):
    help = 'Archive ou purge les vieux logs d\'audit'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Nombre de jours avant archivage (défaut: 90)'
        )
        parser.add_argument(
            '--archive-path',
            type=str,
            default='audit_logs_archive.json',
            help='Chemin du fichier d\'archive'
        )
        parser.add_argument(
            '--purge-only',
            action='store_true',
            help='Purger sans archiver (DANGEREUX)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans exécution'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        archive_path = options['archive_path']
        purge_only = options['purge_only']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        # Récupérer les vieux logs
        old_logs = AuditLog.objects.filter(created_at__lt=cutoff_date)
        count = old_logs.count()
        
        if count == 0:
            self.stdout.write(self.style.SUCCESS('Aucun log à archiver.'))
            return
        
        self.stdout.write(f'{count} logs trouvés avant le {cutoff_date.date()}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('MODE SIMULATION - Aucune action effectuée'))
            for log in old_logs[:5]:
                self.stdout.write(f'  - {log}')
            return
        
        # Archivage (sauf si purge-only)
        if not purge_only:
            self.stdout.write(f'Archivage vers {archive_path}...')
            logs_data = []
            for log in old_logs:
                logs_data.append({
                    'id': log.id,
                    'created_at': log.created_at.isoformat(),
                    'action': log.action,
                    'severity': log.severity,
                    'user_email': log.user_email,
                    'user_role': log.user_role,
                    'university': log.university.nom if log.university else None,
                    'target_type': log.target_type,
                    'target_id': log.target_id,
                    'target_repr': log.target_repr,
                    'previous_data': log.previous_data,
                    'new_data': log.new_data,
                    'ip_address': str(log.ip_address) if log.ip_address else None,
                    'request_path': log.request_path,
                    'request_method': log.request_method,
                    'description': log.description,
                })
            
            # Écrire dans le fichier (append ou créer)
            mode = 'a' if os.path.exists(archive_path) else 'w'
            with open(archive_path, mode) as f:
                if mode == 'w':
                    f.write('[\n')
                else:
                    # Retirer le ] final et ajouter une virgule
                    with open(archive_path, 'r+') as f_read:
                        f_read.seek(0, 2)  # Fin du fichier
                        pos = f_read.tell()
                        while pos > 0:
                            pos -= 1
                            f_read.seek(pos)
                            if f_read.read(1) == ']':
                                f_read.seek(pos)
                                f_read.write(',\n')
                                break
                
                for i, log in enumerate(logs_data):
                    if i > 0 or mode == 'a':
                        f.write(',\n')
                    f.write(json.dumps(log, indent=2, ensure_ascii=False))
                
                f.write('\n]')
            
            self.stdout.write(self.style.SUCCESS(f'Archivage terminé: {count} logs'))
        
        # Suppression
        self.stdout.write(self.style.WARNING(f'Suppression de {count} logs...'))
        deleted = old_logs.delete()
        self.stdout.write(self.style.SUCCESS(f'Suppression terminée: {deleted[0]} entrées'))