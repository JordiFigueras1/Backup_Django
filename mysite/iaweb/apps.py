from django.apps import AppConfig


class IawebConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'iaweb'
    verbose_name = "IADHD-Diagnostic for Human Development"
    
    def ready(self):
        import iaweb.signals
    
