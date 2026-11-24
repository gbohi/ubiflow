"""
Extensions par famille de type de demande.

Le socle des demandes (brouillon, soumission, versions, workflow) est
commun ; une famille (ex. « mission ») y ajoute sa saisie structurée et son
calcul en enregistrant une extension au démarrage de son application :

    extensions.enregistrer('mission', ExtensionMission())

Toutes les méthodes ont un comportement par défaut neutre.
"""

_EXTENSIONS = {}


class Extension:
    # True : le montant de la demande est calculé (la saisie du demandeur est ignorée)
    montant_calcule = False

    def valider(self, type_demande, donnees, complet):
        """Données propres à la famille, normalisées (ajoutées à `Demande.donnees`)."""
        return {}

    def avant_soumission(self, demande, d, premiere):
        """
        Calcul et figement avant enregistrement de la version. Renvoie
        (calcul, note) : calcul stocké dans la version, note ajoutée à l'historique.
        """
        return {}, None

    def apres_version(self, demande, version):
        """Après création de la version soumise (lignes de calcul…)."""

    def apres_approbation(self, demande, infos=None):
        """Après la dernière validation (ex. annulation de la demande d'origine)."""

    def contexte(self, demande):
        """Valeurs supplémentaires pour les conditions du workflow."""
        return {}

    def champs_condition(self, type_demande):
        return []

    def modification_sensible(self, ancien, nouveau):
        """True si une resoumission doit reprendre le circuit au début."""
        return False


NEUTRE = Extension()


def enregistrer(famille, extension):
    _EXTENSIONS[famille] = extension


def pour(type_demande):
    return _EXTENSIONS.get(getattr(type_demande, 'famille', None), NEUTRE)
