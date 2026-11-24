from django.utils import timezone
from rest_framework import serializers

from api.models import ParametreSysteme
from workflow import moteur

from .models import ForfaitTransportHorsPays, PerDiem, TarifKilometrique, TarifTransportVille, TauxChange


class _LigneSerializer(serializers.ModelSerializer):
    """
    Ligne de barème : création seule (jamais de modification). `precedente`
    donne la valeur remplacée pour l'historique (ancien → nouveau montant).
    """
    modifie_par_nom = serializers.SerializerMethodField()
    precedente = serializers.SerializerMethodField()
    en_vigueur = serializers.SerializerMethodField()
    supprimable = serializers.SerializerMethodField()
    VALEUR = 'montant'

    class Meta:
        fields = '__all__'
        read_only_fields = ['modifie_par', 'modifie_le']

    def _cle(self, source):
        get = source.get if isinstance(source, dict) else lambda k, d=None: getattr(source, k, d)
        return {c: get(c) for c in self.Meta.model.CLE}

    def _meme_cle(self, obj):
        return self.Meta.model.objects.filter(**self._cle(obj))

    def get_modifie_par_nom(self, obj):
        return moteur.nom(obj.modifie_par) if obj.modifie_par_id else None

    def get_precedente(self, obj):
        p = self._meme_cle(obj).filter(date_effet__lt=obj.date_effet).order_by('-date_effet', '-id').first()
        return {'id': p.pk, 'date_effet': p.date_effet.isoformat(), 'valeur': str(getattr(p, self.VALEUR)),
                'devise': getattr(p, 'devise', '')} if p else None

    def get_en_vigueur(self, obj):
        actuelle = self._meme_cle(obj).filter(date_effet__lte=timezone.localdate()).order_by('-date_effet', '-id').first()
        return actuelle is not None and actuelle.pk == obj.pk

    def get_supprimable(self, obj):
        return obj.date_effet > timezone.localdate()

    def validate_devise(self, devise):
        devise = (devise or '').strip().upper()
        if len(devise) != 3 or not devise.isalpha():
            raise serializers.ValidationError('Code devise ISO sur 3 lettres (ex. XOF, EUR).')
        return devise

    def validate(self, attrs):
        valeur = attrs.get(self.VALEUR)
        if valeur is not None and valeur <= 0:
            raise serializers.ValidationError({self.VALEUR: 'La valeur doit être positive.'})
        if not (attrs.get('motif') or '').strip():
            raise serializers.ValidationError({'motif': 'Indiquez le motif du changement.'})
        if self.Meta.model.objects.filter(date_effet=attrs['date_effet'], **self._cle(attrs)).exists():
            raise serializers.ValidationError(
                {'date_effet': "Une ligne existe déjà à cette date d'effet : choisissez une autre date."})
        return attrs


class PerDiemSerializer(_LigneSerializer):
    categorie_libelle = serializers.ReadOnlyField(source='categorie.libelle')
    type_mission_libelle = serializers.CharField(source='get_type_mission_display', read_only=True)

    class Meta(_LigneSerializer.Meta):
        model = PerDiem


class TarifKilometriqueSerializer(_LigneSerializer):
    categorie_libelle = serializers.SerializerMethodField()

    class Meta(_LigneSerializer.Meta):
        model = TarifKilometrique

    def get_categorie_libelle(self, obj):
        return obj.categorie.libelle if obj.categorie_id else 'Toutes catégories'


class TarifTransportVilleSerializer(_LigneSerializer):
    ville_libelle = serializers.ReadOnlyField(source='ville.libelle')

    class Meta(_LigneSerializer.Meta):
        model = TarifTransportVille


class ForfaitTransportHorsPaysSerializer(_LigneSerializer):
    class Meta(_LigneSerializer.Meta):
        model = ForfaitTransportHorsPays


class TauxChangeSerializer(_LigneSerializer):
    VALEUR = 'taux'

    class Meta(_LigneSerializer.Meta):
        model = TauxChange

    def validate_devise(self, devise):
        devise = super().validate_devise(devise)
        if devise == ParametreSysteme.charger().devise_reference:
            raise serializers.ValidationError("C'est la devise de référence (taux 1).")
        return devise


class ParametreSystemeSerializer(serializers.ModelSerializer):
    modifiable_devise = serializers.SerializerMethodField()

    class Meta:
        model = ParametreSysteme
        fields = ['devise_reference', 'taille_max_piece_mo', 'updated_at', 'modifiable_devise']
        read_only_fields = ['updated_at']

    def get_modifiable_devise(self, obj):
        from demandes.models import Demande
        return not Demande.objects.filter(reference__isnull=False).exists()

    def validate_devise_reference(self, devise):
        devise = (devise or '').strip().upper()
        if len(devise) != 3 or not devise.isalpha():
            raise serializers.ValidationError('Code devise ISO sur 3 lettres (ex. XOF).')
        if self.instance and devise != self.instance.devise_reference and not self.get_modifiable_devise(self.instance):
            raise serializers.ValidationError(
                "Des demandes ont déjà été soumises : la devise de référence ne peut plus être changée.")
        return devise

    def validate_taille_max_piece_mo(self, v):
        if not 1 <= v <= 100:
            raise serializers.ValidationError('Entre 1 et 100 Mo.')
        return v
