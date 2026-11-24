"""Extension « annulation » : une demande d'annulation approuvée annule la demande d'origine (§4.3)."""
from demandes.extensions import Extension


class ExtensionAnnulation(Extension):
    def apres_approbation(self, demande, infos=None):
        from .services import annuler_apres_approbation
        if demande.demande_parent_id:
            annuler_apres_approbation(demande.demande_parent, demande, infos)
