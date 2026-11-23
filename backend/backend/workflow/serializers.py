from django.db import transaction
from rest_framework import serializers

from . import conditions
from .models import Delegation, Etape, RegleDesignation, Tache, VersionWorkflow
from .moteur import nom


class RegleDesignationSerializer(serializers.ModelSerializer):
    responsabilite_libelle = serializers.ReadOnlyField(source='responsabilite.libelle')
    personne_nom = serializers.SerializerMethodField()
    mode_libelle = serializers.CharField(source='get_mode_display', read_only=True)
    relation_libelle = serializers.CharField(source='get_relation_display', read_only=True)
    perimetre_libelle = serializers.CharField(source='get_perimetre_display', read_only=True)

    class Meta:
        model = RegleDesignation
        exclude = ['etape']

    def get_personne_nom(self, obj):
        return nom(obj.personne) if obj.personne_id else None


class EtapeSerializer(serializers.ModelSerializer):
    regles = RegleDesignationSerializer(many=True, required=False)
    description_condition = serializers.SerializerMethodField()

    class Meta:
        model = Etape
        fields = '__all__'

    def get_description_condition(self, obj):
        libelles = {c['code']: c['libelle'] for c in conditions.champs_disponibles(obj.version.type_demande)}
        return conditions.decrire(obj.condition, libelles)

    def validate_actions_autorisees(self, valeur):
        if not isinstance(valeur, list) or set(valeur) - set(Etape.ACTIONS):
            raise serializers.ValidationError("Actions possibles : approuver, rejeter, retourner.")
        if 'approuver' not in valeur:
            raise serializers.ValidationError("L'action « approuver » est obligatoire.")
        return valeur

    def validate(self, attrs):
        version = attrs.get('version', getattr(self.instance, 'version', None))
        if version is not None and not version.modifiable:
            raise serializers.ValidationError("Version publiée : dupliquez-la pour la modifier.")
        if self.instance is not None and 'version' in attrs and attrs['version'] != self.instance.version:
            raise serializers.ValidationError("Une étape ne change pas de version.")
        if 'condition' in attrs:
            conditions.valider(attrs['condition'] or None, version.type_demande if version else None)
        champs = attrs.get('champs_modifiables')
        if champs:
            codes = set(version.type_demande.champs.values_list('code', flat=True)) | {'montant_approuve'}
            inconnus = set(champs) - codes
            if inconnus:
                raise serializers.ValidationError({'champs_modifiables': f"Champs inconnus : {', '.join(inconnus)}"})
        return attrs

    def _enregistrer_regles(self, etape, regles):
        if regles is None:
            return
        etape.regles.all().delete()
        for i, r in enumerate(regles, start=1):
            RegleDesignation.objects.create(etape=etape, ordre=i, **{k: v for k, v in r.items() if k != 'ordre'})

    def create(self, validated_data):
        regles = validated_data.pop('regles', [])
        if 'actions_autorisees' not in validated_data:
            validated_data['actions_autorisees'] = list(Etape.ACTIONS)
        with transaction.atomic():
            etape = super().create(validated_data)
            self._enregistrer_regles(etape, regles)
        return etape

    def update(self, instance, validated_data):
        regles = validated_data.pop('regles', None)
        with transaction.atomic():
            etape = super().update(instance, validated_data)
            self._enregistrer_regles(etape, regles)
        return etape


class VersionWorkflowSerializer(serializers.ModelSerializer):
    etapes = EtapeSerializer(many=True, read_only=True)
    type_code = serializers.ReadOnlyField(source='type_demande.code')
    type_libelle = serializers.ReadOnlyField(source='type_demande.libelle')
    etat_libelle = serializers.CharField(source='get_etat_display', read_only=True)
    publiee_par_nom = serializers.SerializerMethodField()
    nb_demandes = serializers.SerializerMethodField()

    class Meta:
        model = VersionWorkflow
        fields = '__all__'
        read_only_fields = ['numero', 'etat', 'publiee_le', 'publiee_par', 'cree_par']

    def get_publiee_par_nom(self, obj):
        return nom(obj.publiee_par) if obj.publiee_par_id else None

    def get_nb_demandes(self, obj):
        return obj.demandes.count()

    def validate(self, attrs):
        if self.instance is not None and not self.instance.modifiable:
            raise serializers.ValidationError("Version publiée : dupliquez-la pour la modifier.")
        return attrs


class TacheSerializer(serializers.ModelSerializer):
    demande = serializers.SerializerMethodField()
    etape = serializers.ReadOnlyField(source='etape_instance.etape.libelle')
    actions_autorisees = serializers.ReadOnlyField(source='etape_instance.etape.actions_autorisees')
    champs_modifiables = serializers.ReadOnlyField(source='etape_instance.etape.champs_modifiables')
    valideur_nom = serializers.SerializerMethodField()
    pour_compte_de = serializers.SerializerMethodField()
    etat_libelle = serializers.CharField(source='get_etat_display', read_only=True)

    class Meta:
        model = Tache
        fields = ['id', 'etat', 'etat_libelle', 'decision', 'demande', 'etape', 'actions_autorisees',
                  'champs_modifiables', 'valideur', 'valideur_nom', 'pour_compte_de', 'auto_validation',
                  'ouverte_le', 'traitee_le']

    def get_demande(self, obj):
        d = obj.etape_instance.instance.demande
        return {'id': d.pk, 'reference': d.reference, 'objet': d.objet, 'type_libelle': d.type_demande.libelle,
                'type_code': d.type_demande.code, 'demandeur': nom(d.demandeur),
                'montant_demande': d.montant_demande, 'devise': d.devise, 'statut': d.statut,
                'soumise_le': d.soumise_le}

    def get_valideur_nom(self, obj):
        return nom(obj.valideur)

    def get_pour_compte_de(self, obj):
        user = self.context['request'].user
        return nom(obj.valideur) if obj.valideur_id != user.pk else None


class DelegationSerializer(serializers.ModelSerializer):
    delegant_nom = serializers.SerializerMethodField()
    delegataire_nom = serializers.SerializerMethodField()
    etat = serializers.ReadOnlyField()
    types_demande_libelles = serializers.SerializerMethodField()
    responsabilites_libelles = serializers.SerializerMethodField()

    class Meta:
        model = Delegation
        fields = '__all__'
        read_only_fields = ['revoquee', 'revoquee_le', 'cree_par']
        extra_kwargs = {'delegant': {'required': False}}

    def get_delegant_nom(self, obj):
        return nom(obj.delegant)

    def get_delegataire_nom(self, obj):
        return nom(obj.delegataire)

    def get_types_demande_libelles(self, obj):
        return [t.libelle for t in obj.types_demande.all()]

    def get_responsabilites_libelles(self, obj):
        return [r.libelle for r in obj.responsabilites.all()]

    def validate(self, attrs):
        delegant = attrs.get('delegant') or self.context['request'].user
        attrs['delegant'] = delegant
        if attrs['delegataire'].pk == delegant.pk:
            raise serializers.ValidationError({'delegataire': 'On ne peut pas se déléguer à soi-même.'})
        if not attrs['delegataire'].is_active:
            raise serializers.ValidationError({'delegataire': "Ce collaborateur n'est pas actif."})
        if attrs['date_fin'] < attrs['date_debut']:
            raise serializers.ValidationError({'date_fin': 'La date de fin doit suivre la date de début.'})
        return attrs
