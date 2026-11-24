from rest_framework import serializers

from workflow import moteur

from .models import Reglement, Reversement


def _nom(u):
    return moteur.nom(u) if u else None


class ReglementSerializer(serializers.ModelSerializer):
    mode_libelle = serializers.CharField(source='get_mode_display', read_only=True)
    enregistre_par_nom = serializers.SerializerMethodField()
    annule_par_nom = serializers.SerializerMethodField()
    justificatif_nom = serializers.ReadOnlyField(source='justificatif.nom_origine')

    class Meta:
        model = Reglement
        fields = ['id', 'demande', 'montant', 'devise', 'taux_change', 'montant_ref', 'date_paiement', 'mode',
                  'mode_libelle', 'reference', 'beneficiaire', 'justificatif', 'justificatif_nom', 'enregistre_par_nom',
                  'enregistre_le', 'annule', 'annule_par_nom', 'annule_le', 'motif_annulation']

    def get_enregistre_par_nom(self, obj):
        return _nom(obj.enregistre_par)

    def get_annule_par_nom(self, obj):
        return _nom(obj.annule_par)


class ReversementSerializer(serializers.ModelSerializer):
    etat_libelle = serializers.CharField(source='get_etat_display', read_only=True)
    origine_libelle = serializers.CharField(source='get_origine_display', read_only=True)
    mode_libelle = serializers.CharField(source='get_mode_display', read_only=True)
    traite_par_nom = serializers.SerializerMethodField()
    justificatif_nom = serializers.ReadOnlyField(source='justificatif.nom_origine')
    demande_reference = serializers.ReadOnlyField(source='demande.reference')
    demande_objet = serializers.ReadOnlyField(source='demande.objet')
    demande_type = serializers.ReadOnlyField(source='demande.type_demande.libelle')
    demandeur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Reversement
        fields = ['id', 'demande', 'demande_reference', 'demande_objet', 'demande_type', 'demandeur_nom', 'montant_du',
                  'devise', 'origine', 'origine_libelle', 'motif', 'etat', 'etat_libelle', 'cree_le', 'percu_le', 'mode',
                  'mode_libelle', 'reference', 'justificatif', 'justificatif_nom', 'motif_abandon', 'traite_par_nom',
                  'traite_le']

    def get_traite_par_nom(self, obj):
        return _nom(obj.traite_par)

    def get_demandeur_nom(self, obj):
        return _nom(obj.demande.demandeur)
