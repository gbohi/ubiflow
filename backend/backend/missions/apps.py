from django.apps import AppConfig


class MissionsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'missions'
    verbose_name = 'Missions'

    def ready(self):
        from demandes import extensions
        from .extension import ExtensionMission
        extensions.enregistrer('mission', ExtensionMission())
