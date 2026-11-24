"""python manage.py taches_planifiees — rappels, escalades, rappels de clôture (à lancer toutes les heures)."""
from django.core.management.base import BaseCommand

from workflow.services_planifies import rappeler_clotures, traiter_taches


class Command(BaseCommand):
    help = "Rappels et escalades des validations, rappels de clôture des missions."

    def handle(self, *args, **options):
        rappels, escalades = traiter_taches()
        clotures = rappeler_clotures()
        self.stdout.write(f"{rappels} rappel(s), {escalades} escalade(s), {clotures} rappel(s) de clôture.")
