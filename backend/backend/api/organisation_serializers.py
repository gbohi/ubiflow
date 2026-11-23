"""Sérialiseurs du lot « Organisation » : responsabilités, N+1, véhicule, imports."""
from django.db.models import Q
from rest_framework import serializers

from .models import (
    AffectationHierarchique, AffectationResponsabilite, ImportCollaborateurs, Responsabilite,
    SituationVehicule, User,
)
from .serializers import _PeriodeMixin


def _nom(user):
    return f"{user.nom} {user.prenom}".strip() or user.username if user else None


class _AuditMixin(serializers.ModelSerializer):
    """Champs d'audit en lecture seule (renseignés par la vue)."""

    def get_fields(self):
        champs = super().get_fields()
        for nom in ('user_created', 'user_updated', 'created_at', 'updated_at'):
            if nom in champs:
                champs[nom].read_only = True
        return champs


# ── Responsabilités ────────────────────────────────────────────

class ResponsabiliteSerializer(_AuditMixin):
    portee_libelle = serializers.CharField(source='get_portee_display', read_only=True)
    nb_titulaires = serializers.SerializerMethodField()

    class Meta:
        model = Responsabilite
        fields = '__all__'
        read_only_fields = ['systeme']

    def get_nb_titulaires(self, obj):
        from .organisation import date_du_jour, filtre_en_cours
        return obj.affectations.filter(filtre_en_cours(date_du_jour())).values('user').distinct().count()

    def validate_code(self, code):
        code = (code or '').strip().upper().replace(' ', '_')
        if not code:
            raise serializers.ValidationError("Le code est obligatoire.")
        inst = self.instance
        if inst is not None and inst.systeme and code != inst.code:
            raise serializers.ValidationError("Le code d'une responsabilité système ne peut pas être modifié.")
        doublon = Responsabilite.objects.filter(code=code)
        if inst is not None:
            doublon = doublon.exclude(pk=inst.pk)
        if doublon.exists():
            raise serializers.ValidationError(f"Le code « {code} » existe déjà.")
        return code

    def validate(self, attrs):
        inst = self.instance
        if inst is not None and inst.systeme:
            if 'portee' in attrs and attrs['portee'] != inst.portee:
                raise serializers.ValidationError(
                    {'portee': "La portée d'une responsabilité système ne peut pas être modifiée."})
            if attrs.get('actif') is False:
                raise serializers.ValidationError(
                    {'actif': "Une responsabilité système ne peut pas être désactivée."})
        if inst is not None and 'portee' in attrs and attrs['portee'] != inst.portee \
                and inst.affectations.exists():
            raise serializers.ValidationError(
                {'portee': "Des titulaires sont déjà affectés : la portée ne peut plus être modifiée."})
        return attrs


class AffectationResponsabiliteSerializer(_PeriodeMixin, _AuditMixin):
    """Titulaire d'une responsabilité (daté, périmètre selon la portée)."""
    libelle_periode = 'affectation de cette responsabilité'
    user_nom = serializers.SerializerMethodField()
    user_matricule = serializers.ReadOnlyField(source='user.username')
    responsabilite_code = serializers.ReadOnlyField(source='responsabilite.code')
    responsabilite_libelle = serializers.ReadOnlyField(source='responsabilite.libelle')
    portee = serializers.ReadOnlyField(source='responsabilite.portee')
    departement_libelle = serializers.ReadOnlyField(source='departement.libelle_service')
    agence_libelle = serializers.ReadOnlyField(source='agence.nom_agence')

    class Meta:
        model = AffectationResponsabilite
        fields = '__all__'

    def get_user_nom(self, obj):
        return _nom(obj.user)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = self.instance
        val = lambda k: attrs.get(k, getattr(inst, k, None))
        resp, user = val('responsabilite'), val('user')
        dept, agence = val('departement'), val('agence')
        debut, fin = val('date_debut'), val('date_fin')

        if inst is None and resp is not None and not resp.actif:
            raise serializers.ValidationError({'responsabilite': "Cette responsabilité est désactivée."})
        if resp.portee == Responsabilite.PORTEE_DEPARTEMENT:
            if dept is None:
                raise serializers.ValidationError({'departement': "Choisissez le département concerné."})
            if agence is not None:
                raise serializers.ValidationError({'agence': "Cette responsabilité porte sur un département."})
        elif resp.portee == Responsabilite.PORTEE_AGENCE:
            if agence is None:
                raise serializers.ValidationError({'agence': "Choisissez l'agence concernée."})
            if dept is not None:
                raise serializers.ValidationError({'departement': "Cette responsabilité porte sur une agence."})
        elif dept is not None or agence is not None:
            raise serializers.ValidationError("Cette responsabilité concerne toute l'entreprise : "
                                              "ni département ni agence.")

        # Chevauchement : même personne, même responsabilité, même périmètre ; et si un
        # seul titulaire est autorisé, aucun autre titulaire sur la période.
        autres = AffectationResponsabilite.objects.filter(responsabilite=resp, departement=dept, agence=agence)
        if inst is not None:
            autres = autres.exclude(pk=inst.pk)
        autres = autres.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=debut))
        if fin:
            autres = autres.filter(date_debut__lte=fin)
        if autres.filter(user=user).exists():
            raise serializers.ValidationError("Ce collaborateur tient déjà cette responsabilité sur cette période.")
        if not resp.multiple:
            conflit = autres.exclude(user=user).select_related('user').first()
            if conflit:
                raise serializers.ValidationError(
                    f"« {resp.libelle} » n'admet qu'un titulaire : {_nom(conflit.user)} l'occupe déjà sur "
                    "cette période. Renseignez d'abord sa date de fin.")
        return attrs


# ── Hiérarchie (N+1) ───────────────────────────────────────────

class AffectationHierarchiqueSerializer(_PeriodeMixin, _AuditMixin):
    periode_exclusive = True
    libelle_periode = 'affectation hiérarchique'
    proprietaire = 'du collaborateur'
    user_nom = serializers.SerializerMethodField()
    responsable_nom = serializers.SerializerMethodField()
    responsable_matricule = serializers.ReadOnlyField(source='responsable.username')
    mode_libelle = serializers.CharField(source='get_mode_display', read_only=True)

    class Meta:
        model = AffectationHierarchique
        fields = '__all__'

    def get_user_nom(self, obj):
        return _nom(obj.user)

    def get_responsable_nom(self, obj):
        return _nom(obj.responsable)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        inst = self.instance
        val = lambda k: attrs.get(k, getattr(inst, k, None))
        mode, resp, user = val('mode'), val('responsable'), val('user')
        if mode == AffectationHierarchique.MODE_DESIGNE:
            if resp is None:
                raise serializers.ValidationError({'responsable': "Choisissez le N+1 désigné."})
            if user is not None and resp.pk == user.pk:
                raise serializers.ValidationError({'responsable': "Un collaborateur ne peut pas être son propre N+1."})
        elif resp is not None:
            attrs['responsable'] = None
        if val('exceptionnelle') and not (val('motif') or '').strip():
            raise serializers.ValidationError({'motif': "Le motif est obligatoire pour une réaffectation exceptionnelle."})
        return attrs


class ReaffectationSerializer(serializers.Serializer):
    """Réaffectation exceptionnelle du N+1 (administrateurs) : ferme la ligne en cours."""
    mode = serializers.ChoiceField(choices=AffectationHierarchique.MODES)
    responsable = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True),
                                                     required=False, allow_null=True)
    date_effet = serializers.DateField()
    motif = serializers.CharField(max_length=255)

    def validate_motif(self, motif):
        if not motif.strip():
            raise serializers.ValidationError("Le motif est obligatoire.")
        return motif.strip()


# ── Véhicule ───────────────────────────────────────────────────

class SituationVehiculeSerializer(_PeriodeMixin, _AuditMixin):
    periode_exclusive = True
    libelle_periode = 'situation de véhicule'
    proprietaire = 'du collaborateur'

    class Meta:
        model = SituationVehicule
        fields = '__all__'


# ── Imports ────────────────────────────────────────────────────

class ImportCollaborateursSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = ImportCollaborateurs
        fields = '__all__'

    def get_auteur_nom(self, obj):
        return _nom(obj.auteur)
