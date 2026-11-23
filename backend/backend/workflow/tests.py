"""
Scénarios du moteur de workflow (lot 2), sur le type « Frais de réception
client » (FRC) et son circuit initial : N+1 → DAF → DG si montant > 1 000 000.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APITestCase

from api.models import AffectationResponsabilite, Responsabilite, Service, Statut, User, UserService
from demandes.models import Demande, Document, ExigencePiece, TypeDemande, TypePiece
from notifications.models import Notification

from . import conditions, parametrage
from .models import Action, Delegation, Etape, RegleDesignation, Tache, VersionWorkflow

J0 = date(2026, 1, 1)
DONNEES = {'date_reception': '2026-12-10', 'client': 'SOTRA', 'nombre_participants': 4, 'lieu': 'Abidjan',
           'justification': 'Négociation du contrat annuel'}


def h(d):
    return timezone.make_aware(datetime.combine(d, time.min))


class ConditionsTests(TestCase):
    def test_operateurs(self):
        ctx = {'montant_demande_ref': Decimal('1500000'), 'categorie': 3, 'champ.lieu': 'Abidjan',
               'departement': 7, 'departement__arbre': [7, 2, 1], 'agence': None}
        ev = conditions.evaluer
        self.assertTrue(ev({'champ': 'montant_demande_ref', 'op': '>', 'valeur': 1000000}, ctx))
        self.assertFalse(ev({'champ': 'montant_demande_ref', 'op': '≤', 'valeur': '1000000'}, ctx))
        self.assertTrue(ev({'champ': 'categorie', 'op': 'dans', 'valeur': [1, 3]}, ctx))
        self.assertTrue(ev({'champ': 'champ.lieu', 'op': '=', 'valeur': 'abidjan'}, ctx))
        self.assertTrue(ev({'champ': 'departement', 'op': 'sous', 'valeur': 2}, ctx))
        self.assertFalse(ev({'champ': 'departement', 'op': 'sous', 'valeur': 9}, ctx))
        self.assertTrue(ev({'champ': 'agence', 'op': 'vide'}, ctx))
        self.assertTrue(ev({'et': [{'champ': 'categorie', 'op': '=', 'valeur': 3},
                                   {'ou': [{'champ': 'agence', 'op': 'non_vide'},
                                           {'champ': 'montant_demande_ref', 'op': '≥', 'valeur': 1500000}]}]}, ctx))
        self.assertTrue(ev(None, ctx))

    def test_validation(self):
        with self.assertRaises(Exception):
            conditions.valider({'champ': 'inconnu', 'op': '=', 'valeur': 1})
        with self.assertRaises(Exception):
            conditions.valider({'champ': 'montant_demande_ref', 'op': '>', 'valeur': ''})
        conditions.valider({'et': [{'champ': 'montant_demande_ref', 'op': '>', 'valeur': 5}]})


class Base(APITestCase):
    def setUp(self):
        self.actif = Statut.objects.get(libelle_statut='Actif')
        self.resp_dept = Responsabilite.objects.get(code='RESP_DEPARTEMENT')
        self.direction = Service.objects.create(libelle_service='Direction générale')
        self.finances = Service.objects.create(libelle_service='Finances', parent=self.direction)
        self.compta = Service.objects.create(libelle_service='Comptabilité', parent=self.finances)
        self.dg = self.user('dg', self.direction)
        self.daf = self.user('daf', self.finances)
        self.chef = self.user('chef', self.compta)
        self.agent = self.user('agent', self.compta)
        self.autre = self.user('autre', self.compta)
        for u, dept in ((self.dg, self.direction), (self.daf, self.finances), (self.chef, self.compta)):
            AffectationResponsabilite.objects.create(user=u, responsabilite=self.resp_dept, departement=dept,
                                                     date_debut=J0)
        AffectationResponsabilite.objects.create(user=self.dg, responsabilite=Responsabilite.objects.get(code='DG'),
                                                 date_debut=J0)
        AffectationResponsabilite.objects.create(user=self.daf, responsabilite=Responsabilite.objects.get(code='DAF'),
                                                 date_debut=J0)
        self.frc = TypeDemande.objects.get(code='FRC')
        self.v1 = VersionWorkflow.objects.get(type_demande=self.frc, etat='publiee')

    def user(self, matricule, dept=None, groupes=('employe',)):
        u = User.objects.create_user(matricule, password='Motdepasse1!', nom=matricule.upper(), prenom='T',
                                     statut=self.actif)
        for g in groupes:
            u.groups.add(Group.objects.get(name=g))
        if dept:
            UserService.objects.create(user=u, service=dept, date_debut=h(J0), statut=self.actif)
        return u

    # ── Raccourcis API ──
    def en(self, user):
        self.client.force_authenticate(user)
        return self

    def creer(self, user=None, montant='500000', donnees=None):
        self.en(user or self.agent)
        r = self.client.post('/api/api/demandes/', {'type_demande': self.frc.pk, 'objet': 'Déjeuner client',
                                                    'montant_demande': montant,
                                                    'donnees': donnees if donnees is not None else DONNEES},
                             format='json')
        self.assertEqual(r.status_code, 201, r.data)
        return r.data['id']

    def soumettre(self, pk, user=None, attendu=200, **data):
        self.en(user or Demande.objects.get(pk=pk).demandeur)
        r = self.client.post(f'/api/api/demandes/{pk}/soumettre/', data, format='json')
        self.assertEqual(r.status_code, attendu, r.data)
        return r.data

    def tache_de(self, pk, user):
        return Tache.objects.get(etape_instance__instance__demande_id=pk, etat='en_attente', valideur=user)

    def agir(self, pk, user, quoi='approuver', attendu=200, tache=None, **data):
        tache = tache or self.tache_de(pk, user)
        self.en(user)
        r = self.client.post(f'/api/api/taches/{tache.pk}/{quoi}/', data, format='json')
        self.assertEqual(r.status_code, attendu, r.data)
        return r.data

    def statut(self, pk):
        return Demande.objects.get(pk=pk).statut


class CircuitStandardTests(Base):
    def test_plan_avant_soumission(self):
        pk = self.creer()
        r = self.client.get(f'/api/api/demandes/{pk}/plan/')
        self.assertEqual(r.status_code, 200, r.data)
        plan = {e['code']: e for e in r.data['plan']}
        self.assertEqual(plan['n_plus_1']['valideurs'][0]['id'], self.chef.pk)
        self.assertEqual(plan['daf']['valideurs'][0]['id'], self.daf.pk)
        self.assertEqual(plan['dg']['statut'], 'sautee')
        self.assertIn('1 000 000', plan['dg']['raison'])
        self.assertEqual(self.statut(pk), 'brouillon')  # rien n'est enregistré

    def test_approbation_complete_et_numerotation(self):
        pk = self.creer()
        d = self.soumettre(pk)
        annee = timezone.localdate().year
        self.assertEqual(d['reference'], f'FRC-{annee}-00001')
        self.assertEqual(d['statut'], 'en_validation')
        self.assertEqual(d['n_plus_1'], self.chef.pk)
        self.assertTrue(Notification.objects.filter(destinataire=self.chef, evenement='validation_attendue').exists())
        self.agir(pk, self.chef)
        self.assertTrue(Notification.objects.filter(destinataire=self.daf, evenement='validation_attendue').exists())
        r = self.agir(pk, self.daf)
        self.assertEqual(r['statut'], 'approuvee')
        demande = Demande.objects.get(pk=pk)
        self.assertEqual(demande.montant_approuve, Decimal('500000'))
        self.assertEqual(demande.statut_financier, 'a_payer')
        self.assertTrue(Notification.objects.filter(destinataire=self.agent, evenement='demande_approuvee').exists())
        types = list(demande.actions.values_list('type', flat=True))
        self.assertEqual(types, ['creation', 'soumission', 'saut', 'approbation', 'approbation', 'approbation_finale'])
        # Numérotation sans trou
        pk2 = self.creer()
        self.assertEqual(self.soumettre(pk2)['reference'], f'FRC-{annee}-00002')

    def test_condition_montant_ajoute_le_dg(self):
        pk = self.creer(montant='2000000')
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf)
        self.assertEqual(self.statut(pk), 'en_validation')
        self.agir(pk, self.dg)
        self.assertEqual(self.statut(pk), 'approuvee')

    def test_controles_soumission(self):
        pk = self.creer(donnees={'client': 'X'})
        r = self.soumettre(pk, attendu=400)
        self.assertIn('date_reception', str(r))
        self.en(self.autre)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/soumettre/').status_code, 403)

    def test_seul_le_valideur_agit_et_visibilite(self):
        pk = self.creer()
        self.soumettre(pk)
        tache = self.tache_de(pk, self.chef)
        self.agir(pk, self.autre, tache=tache, attendu=403)
        self.agir(pk, self.daf, tache=tache, attendu=403)
        self.en(self.autre)
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/').status_code, 403)
        self.en(self.chef)
        r = self.client.get(f'/api/api/demandes/{pk}/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['mes_taches']), 1)
        self.assertEqual(self.client.get('/api/api/taches/').data['count'], 1)

    def test_rejet_motif_obligatoire_puis_duplication(self):
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef, 'rejeter', attendu=400)
        self.agir(pk, self.chef, 'rejeter', motif='Budget épuisé')
        self.assertEqual(self.statut(pk), 'rejetee')
        self.assertTrue(Notification.objects.filter(destinataire=self.agent, evenement='demande_rejetee').exists())
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/soumettre/').status_code, 400)
        r = self.client.post(f'/api/api/demandes/{pk}/dupliquer/')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data['statut'], 'brouillon')
        self.assertEqual(r.data['origine_copie'], pk)
        self.assertEqual(r.data['donnees']['client'], 'SOTRA')

    def test_annulation(self):
        pk = self.creer()
        self.soumettre(pk)
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/annuler/', {}).status_code, 400)
        r = self.client.post(f'/api/api/demandes/{pk}/annuler/', {'motif': 'Réception reportée'})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'annulee')
        self.assertFalse(Tache.objects.filter(etape_instance__instance__demande_id=pk, etat='en_attente').exists())
        self.assertTrue(Notification.objects.filter(destinataire=self.chef, evenement='demande_annulee').exists())
        # Type qui n'autorise pas l'annulation en validation
        self.frc.annulation_demandeur = ['a_corriger']
        self.frc.save()
        pk2 = self.creer()
        self.soumettre(pk2)
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk2}/annuler/', {'motif': 'x'}).status_code, 400)

    def test_brouillon_supprimable_pas_apres_soumission(self):
        pk = self.creer()
        self.assertEqual(self.client.delete(f'/api/api/demandes/{pk}/').status_code, 204)
        pk = self.creer()
        self.soumettre(pk)
        self.en(self.agent)
        self.assertEqual(self.client.delete(f'/api/api/demandes/{pk}/').status_code, 400)


class RetourCorrectionTests(Base):
    def test_reprise_au_debut_par_defaut(self):
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf, 'retourner', motif='Joindre le devis')
        self.assertEqual(self.statut(pk), 'a_corriger')
        self.en(self.agent)
        r = self.client.patch(f'/api/api/demandes/{pk}/', {'donnees': {'lieu': 'Grand-Bassam'}}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.soumettre(pk, motif='Lieu corrigé')
        demande = Demande.objects.get(pk=pk)
        self.assertEqual(demande.versions.count(), 2)
        self.assertEqual(demande.instances.count(), 2)
        self.tache_de(pk, self.chef)  # le circuit repart du N+1

    def test_reprise_a_l_etape_du_retour(self):
        self.v1.reprise_apres_correction = 'etape_retour_autorisee'
        self.v1.save()
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf, 'retourner', motif='Préciser le client')
        self.en(self.agent).client.patch(f'/api/api/demandes/{pk}/', {'donnees': {'client': 'SOTRA SA'}},
                                         format='json')
        self.soumettre(pk)
        instance = Demande.objects.get(pk=pk).instances.get(cycle=2)
        self.assertTrue(instance.etapes.get(etape__code='n_plus_1').reprise)
        self.tache_de(pk, self.daf)  # reprise directe au DAF
        self.assertFalse(Tache.objects.filter(etape_instance__instance=instance, valideur=self.chef).exists())

    def test_modification_sensible_reprend_au_debut(self):
        self.v1.reprise_apres_correction = 'etape_retour_autorisee'
        self.v1.save()
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf, 'retourner', motif='Trop de participants')
        self.en(self.agent).client.patch(f'/api/api/demandes/{pk}/', {'donnees': {'nombre_participants': 2}},
                                         format='json')
        self.soumettre(pk)
        self.tache_de(pk, self.chef)
        self.assertIn('sensible', Demande.objects.get(pk=pk).actions.filter(type='resoumission').last().motif)


class DelegationTests(Base):
    def test_delegataire_valide_pour_le_compte_du_delegant(self):
        self.en(self.daf)
        r = self.client.post('/api/api/delegations/', {'delegataire': self.autre.pk, 'date_debut': str(J0),
                                                       'date_fin': str(timezone.localdate() + timedelta(days=5))})
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(Notification.objects.filter(destinataire=self.autre, evenement='delegation_recue').exists())
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.en(self.autre)
        self.assertEqual(self.client.get('/api/api/taches/').data['count'], 1)
        self.agir(pk, self.autre, tache=self.tache_de(pk, self.daf))
        action = Action.objects.filter(demande_id=pk, type='approbation').last()
        self.assertEqual((action.auteur_reel, action.pour_compte_de), (self.autre, self.daf))
        self.assertEqual(self.statut(pk), 'approuvee')

    def test_delegataire_demandeur_et_revocation(self):
        delegation = Delegation.objects.create(delegant=self.chef, delegataire=self.agent, date_debut=J0,
                                               date_fin=timezone.localdate())
        pk = self.creer()  # l'agent est demandeur : il ne peut pas valider sa demande par délégation
        self.soumettre(pk)
        self.agir(pk, self.agent, tache=self.tache_de(pk, self.chef), attendu=403)
        delegation.delegataire = self.autre
        delegation.save()
        self.en(self.chef)
        self.assertEqual(self.client.post(f'/api/api/delegations/{delegation.pk}/revoquer/').status_code, 200)
        self.agir(pk, self.autre, tache=self.tache_de(pk, self.chef), attendu=403)

    def test_delegation_pour_autrui_reservee(self):
        self.en(self.agent)
        r = self.client.post('/api/api/delegations/', {'delegant': self.daf.pk, 'delegataire': self.autre.pk,
                                                       'date_debut': str(J0), 'date_fin': str(J0)})
        self.assertEqual(r.status_code, 403)


class ReglesEtapesTests(Base):
    """Paramètres d'étape : auto-validation, même valideur, parallèle, introuvable."""

    def version(self, *etapes):
        """Publie une nouvelle version avec les étapes [(code, {etape}, [regles])]."""
        v = parametrage.nouvelle_version(self.frc, self.dg)
        for i, (code, attrs, regles) in enumerate(etapes, start=1):
            e = Etape.objects.create(version=v, ordre=i, code=code, libelle=code.upper(),
                                     actions_autorisees=['approuver', 'rejeter', 'retourner'], **attrs)
            for j, r in enumerate(regles, start=1):
                RegleDesignation.objects.create(etape=e, ordre=j, **r)
        return parametrage.publier(v, self.dg)

    def daf_regle(self):
        return {'mode': 'responsabilite', 'responsabilite': Responsabilite.objects.get(code='DAF')}

    def test_auto_validation_manuelle(self):
        self.version(('daf', {'auto_validation_demandeur': 'manuelle'}, [self.daf_regle()]))
        pk = self.creer(user=self.daf)
        self.soumettre(pk)
        tache = self.tache_de(pk, self.daf)
        self.assertTrue(tache.auto_validation)
        self.agir(pk, self.daf)
        self.assertTrue(Action.objects.get(demande_id=pk, type='approbation').auto_validation)
        self.assertEqual(self.statut(pk), 'approuvee')

    def test_auto_validation_automatique_sauter_remonter(self):
        self.version(('daf', {'auto_validation_demandeur': 'automatique'}, [self.daf_regle()]))
        pk = self.creer(user=self.daf)
        self.soumettre(pk)
        self.assertEqual(self.statut(pk), 'approuvee')
        self.assertTrue(Action.objects.filter(demande_id=pk, type='auto_approbation').exists())

        self.version(('daf', {'auto_validation_demandeur': 'sauter'}, [self.daf_regle()]),
                     ('dg', {}, [{'mode': 'responsabilite', 'responsabilite': Responsabilite.objects.get(code='DG')}]))
        pk = self.creer(user=self.daf)
        self.soumettre(pk)
        self.tache_de(pk, self.dg)

        self.version(('daf', {'auto_validation_demandeur': 'remonter'}, [self.daf_regle()]))
        pk = self.creer(user=self.daf)
        self.soumettre(pk)
        self.tache_de(pk, self.dg)  # N+1 du DAF = responsable de la Direction générale

    def test_meme_valideur_deja_passe(self):
        regle_chef = {'mode': 'personne', 'personne': self.chef}
        self.version(('n1', {}, [{'mode': 'relation', 'relation': 'n_plus_1'}]),
                     ('controle', {'meme_valideur_deja_passe': 'approbation_automatique'}, [regle_chef]))
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.assertEqual(self.statut(pk), 'approuvee')
        self.assertIn('Déjà approuvée', Action.objects.filter(demande_id=pk, type='auto_approbation').get().motif)

    def test_parallele(self):
        comite = Responsabilite.objects.create(code='COMITE', libelle='Comité', multiple=True)
        membres = [self.dg, self.daf, self.autre]
        for m in membres:
            AffectationResponsabilite.objects.create(user=m, responsabilite=comite, date_debut=J0)
        regle = [{'mode': 'responsabilite', 'responsabilite': comite}]

        self.version(('comite', {'mode': 'parallele', 'regle_parallele': 'un_seul'}, regle))
        pk = self.creer()
        self.soumettre(pk)
        self.assertEqual(Tache.objects.filter(etape_instance__instance__demande_id=pk, etat='en_attente').count(), 3)
        self.agir(pk, self.autre)
        self.assertEqual(self.statut(pk), 'approuvee')
        self.assertEqual(Tache.objects.filter(etape_instance__instance__demande_id=pk, etat='annulee').count(), 2)

        self.version(('comite', {'mode': 'parallele', 'regle_parallele': 'quorum', 'quorum': 2}, regle))
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.dg)
        self.assertEqual(self.statut(pk), 'en_validation')
        self.agir(pk, self.daf)
        self.assertEqual(self.statut(pk), 'approuvee')

        self.version(('comite', {'mode': 'parallele', 'regle_parallele': 'tous'}, regle))
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.dg)
        self.agir(pk, self.daf)
        self.assertEqual(self.statut(pk), 'en_validation')
        self.agir(pk, self.autre, 'rejeter', motif='Non prioritaire')  # un rejet est immédiat
        self.assertEqual(self.statut(pk), 'rejetee')

    def test_sequentiel_plusieurs_valideurs(self):
        self.version(('duo', {}, [{'mode': 'personne', 'personne': self.daf}, {'mode': 'personne', 'personne': self.dg}]))
        pk = self.creer()
        self.soumettre(pk)
        self.assertFalse(Tache.objects.filter(etape_instance__instance__demande_id=pk, valideur=self.dg,
                                              etat='en_attente').exists())
        self.agir(pk, self.daf)
        self.agir(pk, self.dg)
        self.assertEqual(self.statut(pk), 'approuvee')

    def test_valideur_introuvable(self):
        rh = Responsabilite.objects.get(code='RESP_RH')  # aucun titulaire
        admin = self.user('admin1', groupes=('admin',))
        self.version(('rh', {'valideur_introuvable': 'bloquer'}, [{'mode': 'responsabilite', 'responsabilite': rh}]))
        pk = self.creer()
        r = self.soumettre(pk, attendu=400)
        self.assertIn('Aucun valideur', str(r))
        self.assertEqual(self.statut(pk), 'brouillon')
        self.assertTrue(Notification.objects.filter(evenement='workflow_bloque', destinataire=admin).exists())

        self.version(('rh', {'valideur_introuvable': 'sauter'}, [{'mode': 'responsabilite', 'responsabilite': rh}]),
                     ('daf', {}, [self.daf_regle()]))
        pk = self.creer()
        self.soumettre(pk)
        self.tache_de(pk, self.daf)

    def test_responsable_du_departement_du_demandeur(self):
        self.version(('resp', {}, [{'mode': 'responsabilite', 'responsabilite': self.resp_dept,
                                    'perimetre': 'departement_demandeur'}]))
        pk = self.creer()
        self.soumettre(pk)
        self.tache_de(pk, self.chef)

    def test_champs_modifiables_par_le_valideur(self):
        pk = self.creer()
        self.soumettre(pk)
        self.agir(pk, self.chef, modifications={'montant_approuve': '300000'}, attendu=400)  # non autorisé ici
        self.agir(pk, self.chef)
        self.agir(pk, self.daf, modifications={'montant_approuve': '450000'})
        demande = Demande.objects.get(pk=pk)
        self.assertEqual((demande.montant_demande, demande.montant_approuve), (Decimal('500000'), Decimal('450000')))
        self.assertTrue(demande.actions.filter(type='correction').exists())


class ParametrageTests(Base):
    def setUp(self):
        super().setUp()
        self.admin_wf = self.user('adminwf', groupes=('admin_workflow',))

    def test_version_brouillon_publication_et_demandes_engagees(self):
        pk = self.creer()
        self.soumettre(pk)
        self.en(self.admin_wf)
        r = self.client.post('/api/api/versions-workflow/', {'type_demande': self.frc.pk, 'source': self.v1.pk})
        self.assertEqual(r.status_code, 201, r.data)
        v2 = r.data['id']
        self.assertEqual(len(r.data['etapes']), 3)
        # La version publiée n'est pas modifiable
        etape_v1 = self.v1.etapes.first()
        self.assertEqual(self.client.patch(f'/api/api/etapes-workflow/{etape_v1.pk}/', {'libelle': 'X'}).status_code, 400)
        # Une responsabilité de département sans périmètre bloque la publication
        r = self.client.post('/api/api/etapes-workflow/', {
            'version': v2, 'code': 'resp', 'libelle': 'Responsable', 'regles': [
                {'mode': 'responsabilite', 'responsabilite': self.resp_dept.pk, 'perimetre': 'aucun'}]},
            format='json')
        self.assertEqual(r.status_code, 201, r.data)
        self.assertTrue(self.client.get(f'/api/api/versions-workflow/{v2}/controle/').data['erreurs'])
        self.assertEqual(self.client.post(f'/api/api/versions-workflow/{v2}/publier/').status_code, 400)
        self.client.patch(f"/api/api/etapes-workflow/{r.data['id']}/", {'regles': [
            {'mode': 'responsabilite', 'responsabilite': self.resp_dept.pk, 'perimetre': 'departement_demandeur'}]},
            format='json')
        r = self.client.post(f'/api/api/versions-workflow/{v2}/publier/', {'commentaire': 'Ajout du responsable'})
        self.assertEqual(r.status_code, 200, r.data)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.etat, 'archivee')
        # La demande engagée garde la v1
        self.assertEqual(Demande.objects.get(pk=pk).version_workflow, self.v1)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf)
        self.assertEqual(self.statut(pk), 'approuvee')
        # Le journal trace la publication
        from audit.models import JournalActivite
        self.assertTrue(JournalActivite.objects.filter(action='workflow.publication').exists())

    def test_simulation_et_droits(self):
        self.en(self.admin_wf)
        r = self.client.post(f'/api/api/versions-workflow/{self.v1.pk}/simuler/',
                             {'demandeur': self.agent.pk, 'montant': '2500000'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual([e['statut'] for e in r.data['plan']], ['prevue', 'prevue', 'prevue'])
        self.en(self.agent)
        self.assertEqual(self.client.post('/api/api/versions-workflow/', {'type_demande': self.frc.pk}).status_code, 403)
        self.assertEqual(self.client.get('/api/api/champs-condition/', {'type_demande': self.frc.pk}).status_code, 200)

    def test_reaffectation_de_tache(self):
        pk = self.creer()
        self.soumettre(pk)
        tache = self.tache_de(pk, self.chef)
        self.en(self.admin_wf)
        url = f'/api/api/taches/{tache.pk}/reaffecter/'
        self.assertEqual(self.client.post(url, {'valideur': self.autre.pk}).status_code, 400)  # motif
        r = self.client.post(url, {'valideur': self.autre.pk, 'motif': 'Chef en congé maladie'})
        self.assertEqual(r.status_code, 200, r.data)
        self.agir(pk, self.autre)
        self.assertTrue(Action.objects.filter(demande_id=pk, type='reaffectation').exists())

    def test_type_de_demande_parametrable(self):
        self.en(self.admin_wf)
        r = self.client.post('/api/api/types-demande/', {'code': 'abs', 'libelle': 'Autorisation d\'absence',
                                                         'prefixe_reference': 'ABS', 'avec_montant': False,
                                                         'annulation_demandeur': ['en_validation']}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        tid = r.data['id']
        r = self.client.post('/api/api/champs-type/', {'type_demande': tid, 'code': 'motif', 'libelle': 'Motif',
                                                       'nature': 'liste', 'options': [], 'obligatoire': True},
                             format='json')
        self.assertEqual(r.status_code, 400)  # liste sans choix
        r = self.client.post('/api/api/champs-type/', {'type_demande': tid, 'code': 'motif', 'libelle': 'Motif',
                                                       'nature': 'liste', 'options': ['Familial', 'Médical'],
                                                       'obligatoire': True}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        # Sans circuit publié, pas de demande possible
        self.en(self.agent)
        r = self.client.post('/api/api/demandes/', {'type_demande': tid, 'objet': 'x'}, format='json')
        self.assertEqual(r.status_code, 400)
        # Circuit minimal publié → demande sans montant, valeur de liste contrôlée
        v = parametrage.nouvelle_version(TypeDemande.objects.get(pk=tid), self.dg)
        e = Etape.objects.create(version=v, ordre=1, code='n1', libelle='N+1', actions_autorisees=['approuver'])
        RegleDesignation.objects.create(etape=e, mode='relation', relation='n_plus_1')
        parametrage.publier(v, self.dg)
        r = self.client.post('/api/api/demandes/', {'type_demande': tid, 'objet': 'Absence',
                                                    'donnees': {'motif': 'Autre'}}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/api/demandes/', {'type_demande': tid, 'objet': 'Absence',
                                                    'donnees': {'motif': 'Médical'}}, format='json')
        self.assertEqual(r.status_code, 201)
        self.assertEqual(self.soumettre(r.data['id'])['reference'][:4], 'ABS-')
        # Le retour n'est pas autorisé à cette étape
        self.agir(r.data['id'], self.chef, 'retourner', motif='x', attendu=400)


class DocumentsTests(Base):
    def fichier(self, nom='devis.pdf', contenu=b'%PDF-1.4 test'):
        return SimpleUploadedFile(nom, contenu, content_type='application/pdf')

    def test_pieces_jointes(self):
        proforma = TypePiece.objects.get(code='proforma')
        ExigencePiece.objects.filter(type_demande=self.frc).update(obligatoire=True)
        pk = self.creer()
        self.soumettre(pk, attendu=400)  # proforma obligatoire
        self.en(self.agent)
        r = self.client.post(f'/api/api/demandes/{pk}/documents/', {'fichier': self.fichier('a.exe'),
                                                                    'type_piece': proforma.pk})
        self.assertEqual(r.status_code, 400)  # format refusé
        r = self.client.post(f'/api/api/demandes/{pk}/documents/', {'fichier': self.fichier(), 'type_piece': proforma.pk})
        self.assertEqual(r.status_code, 201, r.data)
        doc = r.data['id']
        self.assertEqual(len(r.data['empreinte']), 64)
        self.soumettre(pk)
        self.assertEqual(Document.objects.get(pk=doc).version_contenu.numero, 1)
        # Après soumission : plus de retrait par le demandeur, téléchargement par le valideur
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/documents/{doc}/retirer/', {'motif': 'x'}).status_code, 400)
        self.en(self.chef)
        r = self.client.get(f'/api/api/demandes/{pk}/documents/{doc}/fichier/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b''.join(r.streaming_content), b'%PDF-1.4 test')
        # Le valideur en attente peut joindre une pièce
        r = self.client.post(f'/api/api/demandes/{pk}/documents/', {'fichier': self.fichier('note.pdf')})
        self.assertEqual(r.status_code, 201)
        self.en(self.autre)
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/documents/{doc}/fichier/').status_code, 403)
        # En correction : retrait logique motivé (la pièce reste en base)
        self.agir(pk, self.chef, 'retourner', motif='Devis illisible')
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/documents/{doc}/retirer/', {}).status_code, 400)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/documents/{doc}/retirer/',
                                          {'motif': 'Remplacé'}).status_code, 204)
        self.assertTrue(Document.objects.get(pk=doc).retire)
        self.soumettre(pk, attendu=400)  # le proforma manque de nouveau

    def test_brouillon_retrait_physique_et_commentaire(self):
        pk = self.creer()
        self.en(self.agent)
        doc = self.client.post(f'/api/api/demandes/{pk}/documents/', {'fichier': self.fichier()}).data['id']
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/documents/{doc}/retirer/').status_code, 204)
        self.assertFalse(Document.objects.filter(pk=doc).exists())
        self.soumettre(pk)
        self.en(self.chef)
        r = self.client.post(f'/api/api/demandes/{pk}/commentaires/', {'texte': 'Quel restaurant ?'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(Notification.objects.filter(destinataire=self.agent, evenement='commentaire').exists())
        r = self.client.get(f'/api/api/demandes/{pk}/historique/')
        self.assertIn('commentaire', [a['type'] for a in r.data])


class NotificationsTests(Base):
    def test_compteur_et_lecture(self):
        pk = self.creer()
        self.soumettre(pk)
        self.en(self.chef)
        self.assertEqual(self.client.get('/api/api/notifications/compteur/').data['non_lues'], 1)
        notif = self.client.get('/api/api/notifications/').data['results'][0]
        self.assertEqual(notif['demande'], pk)
        self.client.post(f"/api/api/notifications/{notif['id']}/lire/")
        self.assertEqual(self.client.get('/api/api/notifications/compteur/').data['non_lues'], 0)
        r = self.client.get('/api/api/demandes/compteurs/')
        self.assertEqual(r.data['a_valider'], 1)
