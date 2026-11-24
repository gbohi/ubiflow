from django.apps import AppConfig


class TresorerieConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tresorerie'
    verbose_name = 'Trésorerie'

    def ready(self):
        from demandes import extensions
        from .extension import ExtensionAnnulation
        extensions.enregistrer('annulation', ExtensionAnnulation())
