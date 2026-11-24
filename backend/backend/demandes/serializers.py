from rest_framework import serializers

from workflow import moteur
from workflow.models import Action, Tache

from .models import ChampType, Commentaire, Demande, Document, ExigencePiece, TypeDemande, TypePiece, VersionContenu
from .services import actions_possibles


def _nom(u):
    return moteur.nom(u) if u else None


# ── Paramétrage ────────────────────────────────────────────────

class TypePieceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypePiece
        fields = '__all__'


class ChampTypeSerializer(serializers.ModelSerializer):
    nature_libelle = serializers.CharField(source='get_nature_display', read_only=True)

    class Meta:
        model = ChampType
        fields = '__all__'

    def validate(self, attrs):
        nature = attrs.get('nature', getattr(self.instance, 'nature', None))
        options = attrs.get('options', getattr(self.instance, 'options', []))
        if nature == 'liste' and not options:
            raise serializers.ValidationError({'options': 'Indiquez les choix de la liste.'})
        if options and not (isinstance(options, list) and all(isinstance(o, str) and o.strip() for o in options)):
            raise serializers.ValidationError({'options': 'Liste de libellés attendue.'})
        type_demande = attrs.get('type_demande', getattr(self.instance, 'type_demande', None))
        code = attrs.get('code', getattr(self.instance, 'code', None))
        doublon = ChampType.objects.filter(type_demande=type_demande, code=code)
        if self.instance is not None:
            doublon = doublon.exclude(pk=self.instance.pk)
        if doublon.exists():
            raise serializers.ValidationError({'code': f"Le code « {code} » existe déjà pour ce type."})
        if code in ('objet', 'montant_demande', 'montant_approuve', 'devise'):
            raise serializers.ValidationError({'code': 'Ce code est réservé.'})
        return attrs


class ExigencePieceSerializer(serializers.ModelSerializer):
    type_piece_libelle = serializers.ReadOnlyField(source='type_piece.libelle')
    moment_libelle = serializers.CharField(source='get_moment_display', read_only=True)

    class Meta:
        model = ExigencePiece
        fields = '__all__'

    def validate(self, attrs):
        moment = attrs.get('moment', getattr(self.instance, 'moment', None))
        if moment == 'etape' and not attrs.get('etape_code', getattr(self.instance, 'etape_code', '')):
            raise serializers.ValidationError({'etape_code': "Indiquez le code de l'étape concernée."})
        return attrs


class TypeDemandeSerializer(serializers.ModelSerializer):
    champs = ChampTypeSerializer(many=True, read_only=True)
    exigences = ExigencePieceSerializer(many=True, read_only=True)
    circuit_publie = serializers.SerializerMethodField()

    class Meta:
        model = TypeDemande
        fields = '__all__'

    def get_circuit_publie(self, obj):
        v = moteur.version_publiee(obj)
        return {'id': v.pk, 'numero': v.numero} if v else None

    def validate_code(self, code):
        return code.strip().upper()

    def validate_annulation_demandeur(self, valeur):
        autorises = {'en_validation', 'a_corriger'}
        if not isinstance(valeur, list) or set(valeur) - autorises:
            raise serializers.ValidationError("Statuts possibles : en_validation, a_corriger.")
        return valeur


# ── Demandes ───────────────────────────────────────────────────

class _EtapeEnCoursMixin:
    def get_etape_en_cours(self, obj):
        instance = next((i for i in obj.instances.all() if i.etat == 'en_cours'), None)
        if instance is None:
            return None
        ei = next((e for e in instance.etapes.all() if e.etat == 'en_cours'), None)
        if ei is None:
            return None
        return {'libelle': ei.etape.libelle, 'ordre': ei.ordre,
                'valideurs': [_nom(t.valideur) for t in ei.taches.all() if t.etat == 'en_attente']}


class DemandeListeSerializer(_EtapeEnCoursMixin, serializers.ModelSerializer):
    type_code = serializers.ReadOnlyField(source='type_demande.code')
    type_libelle = serializers.ReadOnlyField(source='type_demande.libelle')
    type_icone = serializers.ReadOnlyField(source='type_demande.icone')
    demandeur_nom = serializers.SerializerMethodField()
    statut_libelle = serializers.CharField(source='get_statut_display', read_only=True)
    statut_financier_libelle = serializers.CharField(source='get_statut_financier_display', read_only=True)
    etape_en_cours = serializers.SerializerMethodField()

    class Meta:
        model = Demande
        fields = ['id', 'reference', 'type_demande', 'type_code', 'type_libelle', 'type_icone', 'demandeur', 'demandeur_nom',
                  'objet', 'montant_demande', 'montant_approuve', 'devise', 'statut', 'statut_libelle',
                  'statut_financier', 'statut_financier_libelle', 'soumise_le', 'approuvee_le', 'created_at',
                  'updated_at', 'etape_en_cours']

    def get_demandeur_nom(self, obj):
        return _nom(obj.demandeur)


class DemandeEcritureSerializer(serializers.Serializer):
    type_demande = serializers.PrimaryKeyRelatedField(queryset=TypeDemande.objects.all(), required=False)
    objet = serializers.CharField(max_length=255, allow_blank=True, required=False)
    montant_demande = serializers.CharField(allow_blank=True, allow_null=True, required=False)
    devise = serializers.CharField(max_length=3, allow_blank=True, required=False)
    donnees = serializers.DictField(required=False)
    mission = serializers.DictField(required=False)
    demande_parent = serializers.PrimaryKeyRelatedField(queryset=Demande.objects.all(), required=False, allow_null=True)

    def validate(self, attrs):
        if 'mission' in attrs:
            attrs['donnees'] = {**attrs.get('donnees', {}), 'mission': attrs.pop('mission')}
        return attrs


class DocumentSerializer(serializers.ModelSerializer):
    type_piece_libelle = serializers.ReadOnlyField(source='type_piece.libelle')
    ajoute_par_nom = serializers.SerializerMethodField()
    retire_par_nom = serializers.SerializerMethodField()
    version_numero = serializers.ReadOnlyField(source='version_contenu.numero')

    class Meta:
        model = Document
        exclude = ['fichier']

    def get_ajoute_par_nom(self, obj):
        return _nom(obj.ajoute_par)

    def get_retire_par_nom(self, obj):
        return _nom(obj.retire_par)


class CommentaireSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()

    class Meta:
        model = Commentaire
        fields = ['id', 'auteur', 'auteur_nom', 'texte', 'creee_le']

    def get_auteur_nom(self, obj):
        return _nom(obj.auteur)


class VersionContenuSerializer(serializers.ModelSerializer):
    cree_par_nom = serializers.SerializerMethodField()
    origine_libelle = serializers.CharField(source='get_origine_display', read_only=True)

    class Meta:
        model = VersionContenu
        exclude = ['demande']

    def get_cree_par_nom(self, obj):
        return _nom(obj.cree_par)


class ActionSerializer(serializers.ModelSerializer):
    type_libelle = serializers.CharField(source='get_type_display', read_only=True)
    auteur_nom = serializers.SerializerMethodField()
    pour_compte_de_nom = serializers.SerializerMethodField()
    etape_libelle = serializers.ReadOnlyField(source='etape_instance.etape.libelle')
    cycle = serializers.ReadOnlyField(source='instance.cycle')

    class Meta:
        model = Action
        fields = ['id', 'type', 'type_libelle', 'auteur_nom', 'pour_compte_de_nom', 'etape_libelle', 'cycle',
                  'motif', 'donnees', 'auto_validation', 'canal', 'horodatage']

    def get_auteur_nom(self, obj):
        return _nom(obj.auteur_reel) or 'Système'

    def get_pour_compte_de_nom(self, obj):
        return _nom(obj.pour_compte_de) if obj.pour_compte_de_id and obj.pour_compte_de_id != obj.auteur_reel_id else None


def circuit(demande):
    """Cycles de validation : étapes, valideurs et décisions (affichage de la progression)."""
    cycles = []
    for instance in demande.instances.all().order_by('cycle'):
        etapes = []
        for ei in instance.etapes.all().order_by('ordre'):
            entree = next((e for e in instance.plan if e['etape'] == ei.etape_id), {})
            etapes.append({
                'id': ei.pk, 'ordre': ei.ordre, 'libelle': ei.etape.libelle, 'etat': ei.etat,
                'etat_libelle': ei.get_etat_display(), 'motif_saut': ei.motif_saut, 'reprise': ei.reprise,
                'mode': ei.etape.mode, 'regle_parallele': ei.etape.regle_parallele, 'raison': entree.get('raison', ''),
                'valideurs_prevus': [v['nom'] for v in entree.get('valideurs', [])],
                'taches': [{'id': t.pk, 'valideur': _nom(t.valideur), 'etat': t.etat, 'decision': t.decision,
                            'traitee_par': _nom(t.traitee_par), 'traitee_le': t.traitee_le,
                            'auto_validation': t.auto_validation} for t in ei.taches.all().order_by('ordre')],
            })
        cycles.append({'cycle': instance.cycle, 'etat': instance.etat, 'etat_libelle': instance.get_etat_display(),
                       'version_workflow': instance.version.numero, 'creee_le': instance.creee_le,
                       'etapes': etapes})
    return cycles


class DemandeDetailSerializer(DemandeListeSerializer):
    cree_par_nom = serializers.SerializerMethodField()
    n_plus_1_nom = serializers.SerializerMethodField()
    departement_libelle = serializers.ReadOnlyField(source='departement.libelle_service')
    agence_libelle = serializers.ReadOnlyField(source='agence.nom_agence')
    categorie_libelle = serializers.ReadOnlyField(source='categorie.libelle')
    champs = serializers.SerializerMethodField()
    pieces_exigees = serializers.SerializerMethodField()
    version_numero = serializers.ReadOnlyField(source='version_courante.numero')
    version_workflow_numero = serializers.ReadOnlyField(source='version_workflow.numero')
    documents = DocumentSerializer(many=True, read_only=True)
    commentaires = CommentaireSerializer(many=True, read_only=True)
    circuit = serializers.SerializerMethodField()
    actions = serializers.SerializerMethodField()
    mes_taches = serializers.SerializerMethodField()
    origine_copie_reference = serializers.ReadOnlyField(source='origine_copie.reference')
    solde = serializers.ReadOnlyField()
    type_famille = serializers.ReadOnlyField(source='type_demande.famille')
    type_parametres = serializers.ReadOnlyField(source='type_demande.parametres')
    mission = serializers.SerializerMethodField()
    calcul = serializers.SerializerMethodField()
    demande_parent_reference = serializers.ReadOnlyField(source='demande_parent.reference')
    demande_parent_type = serializers.ReadOnlyField(source='demande_parent.type_demande.libelle')
    reglements = serializers.SerializerMethodField()
    reversements = serializers.SerializerMethodField()
    rattachees = serializers.SerializerMethodField()
    synthese = serializers.SerializerMethodField()

    class Meta:
        model = Demande
        fields = DemandeListeSerializer.Meta.fields + [
            'cree_par', 'cree_par_nom', 'donnees', 'champs', 'pieces_exigees', 'devise_reference',
            'montant_demande_ref', 'montant_paye', 'montant_reverse', 'solde', 'n_plus_1', 'n_plus_1_nom',
            'departement', 'departement_libelle', 'agence', 'agence_libelle', 'categorie', 'categorie_libelle',
            'version_numero', 'version_workflow_numero', 'documents', 'commentaires', 'circuit', 'actions',
            'mes_taches', 'origine_copie', 'origine_copie_reference', 'demande_parent', 'motif_annulation',
            'annulee_le', 'type_famille', 'type_parametres', 'mission', 'calcul', 'demande_parent_reference',
            'demande_parent_type', 'cloturee_le', 'reglements', 'reversements', 'rattachees', 'synthese',
            'paiement_fractionne']

    paiement_fractionne = serializers.ReadOnlyField(source='type_demande.paiement_fractionne_autorise')

    def get_reglements(self, obj):
        from tresorerie.serializers import ReglementSerializer
        return ReglementSerializer(obj.reglements.select_related('enregistre_par', 'annule_par', 'justificatif'),
                                   many=True).data

    def get_reversements(self, obj):
        from tresorerie.serializers import ReversementSerializer
        return ReversementSerializer(obj.reversements.select_related('demande__type_demande', 'demande__demandeur',
                                                                     'traite_par', 'justificatif'), many=True).data

    def get_rattachees(self, obj):
        """Demandes rattachées (frais complémentaires, annulation), hors brouillons d'autrui."""
        user = self.context['request'].user
        return [{'id': d.pk, 'reference': d.reference, 'type_libelle': d.type_demande.libelle,
                 'type_code': d.type_demande.code, 'objet': d.objet, 'statut': d.statut,
                 'statut_libelle': d.get_statut_display(), 'montant_approuve': d.montant_approuve,
                 'montant_demande': d.montant_demande, 'devise': d.devise}
                for d in obj.demandes_rattachees.select_related('type_demande').order_by('created_at')
                if d.statut != 'brouillon' or d.demandeur_id == user.pk]

    def get_synthese(self, obj):
        if obj.type_demande.famille != 'mission':
            return None
        from tresorerie.services import synthese
        return synthese(obj)

    def get_mission(self, obj):
        return (obj.donnees or {}).get('mission') if obj.type_demande.famille == 'mission' else None

    def get_calcul(self, obj):
        """Récapitulatif figé de la version soumise (ce que le demandeur a vu)."""
        return (obj.version_courante.calcul or None) if obj.version_courante_id else None

    def get_cree_par_nom(self, obj):
        return _nom(obj.cree_par)

    def get_n_plus_1_nom(self, obj):
        return _nom(obj.n_plus_1)

    def get_champs(self, obj):
        return ChampTypeSerializer(obj.type_demande.champs.filter(actif=True), many=True).data

    def get_pieces_exigees(self, obj):
        return ExigencePieceSerializer(obj.type_demande.exigences.all(), many=True).data

    def get_circuit(self, obj):
        return circuit(obj)

    def get_actions(self, obj):
        return actions_possibles(obj, self.context['request'].user)

    def get_mes_taches(self, obj):
        user = self.context['request'].user
        taches = (Tache.objects.filter(etape_instance__instance__demande=obj, etat='en_attente')
                  .filter(moteur.filtre_taches_de(user)).select_related('etape_instance__etape', 'valideur'))
        return [{'id': t.pk, 'etape': t.etape_instance.etape.libelle,
                 'actions_autorisees': t.etape_instance.etape.actions_autorisees,
                 'champs_modifiables': t.etape_instance.etape.champs_modifiables,
                 'pour_compte_de': _nom(t.valideur) if t.valideur_id != user.pk else None,
                 'auto_validation': t.auto_validation} for t in taches]
