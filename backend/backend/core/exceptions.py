"""
Gestionnaire d'exceptions DRF : message clair en français quand une limite de
fréquence est atteinte (connexion, mot de passe oublié…), avec le délai.
"""
import math

from rest_framework.exceptions import Throttled
from rest_framework.views import exception_handler


def gestionnaire_exceptions(exc, context):
    reponse = exception_handler(exc, context)
    if isinstance(exc, Throttled) and reponse is not None:
        attente = exc.wait
        if attente and attente >= 60:
            minutes = math.ceil(attente / 60)
            delai = f"{minutes} minute{'s' if minutes > 1 else ''}"
        elif attente:
            secondes = math.ceil(attente)
            delai = f"{secondes} seconde{'s' if secondes > 1 else ''}"
        else:
            delai = 'quelques minutes'
        reponse.data = {'detail': f"Trop de tentatives. Veuillez réessayer dans {delai}."}
    return reponse
