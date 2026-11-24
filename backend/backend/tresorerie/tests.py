"""
Lot 4 : règlements, statut financier (§4.2), clôture automatique, séparation
des tâches, demandes rattachées (FCM, ANN), annulation après paiement et
reversements.
"""
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from demandes.models import Demande, TypeDemande
from missions.tests import MissionBase
from notifications.models import Notification

from .models import Reglement, Reversement

PAI = {'beneficiaire': 'SODECI', 'mode_paiement': 'Virement', 'motif': 'Facture eau octobre'}


def fichier(nom='recu.pdf'):
    return SimpleUploadedFile(nom, b'%PDF-1.4 test', content_type='application/pdf')


class TresorerieBase(MissionBase):
    def setUp(self):
        super().setUp()
        self.caisse = self.user('caisse', groupes=('comptable',))
        self.finances = self.user('fin', groupes=('admin_finances',))
        self.pai = TypeDemande.objects.get(code='PAI')
        self.ann = TypeDemande.objects.get(code='ANN')
        self.fcm = TypeDemande.objects.get(code='FCM')

    def approuver_frc(self, montant='500000'):
        pk = self.creer(montant=montant)
        self.soumettre(pk)
        self.agir(pk, self.chef)
        self.agir(pk, self.daf)
        return pk

    def approuver(self, pk):
        """Valide toutes les tâches en attente jusqu'à l'approbation finale."""
        for _ in range(6):
            d = Demande.objects.get(pk=pk)
            if d.statut != 'en_validation':
                return d
            tache = d.instances.get(etat='en_cours').etapes.get(etat='en_cours').taches.filter(etat='en_attente').first()
            self.agir(pk, tache.valideur, tache=tache)
        return Demande.objects.get(pk=pk)

    def creer_type(self, type_demande, parent=None, montant=None, donnees=None, objet='Objet', user=None):
        self.en(user or self.agent)
        r = self.client.post('/api/api/demandes/', {
            'type_demande': type_demande.pk, 'objet': objet, 'montant_demande': montant, 'donnees': donnees or {},
            'demande_parent': parent}, format='json')
        return r

    def payer(self, pk, montant, user=None, attendu=201, **autres):
        self.en(user or self.caisse)
        r = self.client.post('/api/api/tresorerie/reglements/', {'demande': pk, 'montant': montant, 'mode': 'virement',
                                                                 **autres}, format='multipart')
        self.assertEqual(r.status_code, attendu, r.data)
        return r.data


class ReglementsTests(TresorerieBase):
    def test_paiement_complet_et_cloture_automatique(self):
        pk = self.approuver_frc()
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier), ('approuvee', 'a_payer'))
        self.assertTrue(Notification.objects.filter(destinataire=self.caisse, evenement='a_payer').exists())
        self.en(self.caisse)
        self.assertEqual(self.client.get('/api/api/tresorerie/a-payer/').data['count'], 1)
        self.assertTrue(self.client.get(f'/api/api/demandes/{pk}/').data['actions']['payer'])
        r = self.payer(pk, '500000', reference='VIR-001')
        self.assertEqual(r['beneficiaire'], 'AGENT T')
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier, d.montant_paye), ('cloturee', 'soldee', Decimal('500000')))
        self.assertTrue(Notification.objects.filter(destinataire=self.agent, evenement='paiement').exists())
        self.assertEqual(self.client.get('/api/api/tresorerie/a-payer/').data['count'], 0)
        self.assertEqual(list(d.actions.values_list('type', flat=True))[-2:], ['paiement', 'cloture'])

    def test_paiement_en_une_fois_si_non_fractionne(self):
        pk = self.approuver_frc()
        self.payer(pk, '200000', attendu=400)
        self.payer(pk, '600000', attendu=400)

    def test_paiements_fractionnes(self):
        self.pai.exigences.filter(moment='paiement').update(obligatoire=False)
        r = self.creer_type(self.pai, montant='300000', donnees=PAI)
        pk = r.data['id']
        self.soumettre(pk)
        self.approuver(pk)
        self.payer(pk, '100000')
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut_financier, d.solde), ('partiellement_payee', Decimal('200000')))
        self.payer(pk, '250000', attendu=400)  # dépasse le reste à payer
        self.payer(pk, '200000')
        self.assertEqual(Demande.objects.get(pk=pk).statut, 'cloturee')

    def test_justificatif_de_paiement_exige(self):
        pk = self.creer_type(self.pai, montant='300000', donnees=PAI).data['id']
        self.soumettre(pk)
        self.approuver(pk)
        self.assertIn('justificatif', self.payer(pk, '300000', attendu=400))
        r = self.payer(pk, '300000', justificatif=fichier())
        self.assertEqual(r['justificatif_nom'], 'recu.pdf')
        self.assertEqual(Demande.objects.get(pk=pk).documents.get().type_piece.code, 'justificatif_paiement')

    def test_droits_et_separation_des_taches(self):
        pk = self.approuver_frc()
        self.payer(pk, '500000', user=self.agent, attendu=403)
        # le DAF est aussi comptable et a approuvé : refusé si la séparation est activée
        self.daf.groups.add(*self.caisse.groups.all())
        self.daf._roles_cache = None
        del self.daf._roles_cache
        self.frc.separation_approbation_paiement = True
        self.frc.save()
        self.payer(pk, '500000', user=self.daf, attendu=403)
        self.payer(pk, '500000')

    def test_annulation_d_un_paiement(self):
        pk = self.approuver_frc()
        r = self.payer(pk, '500000')
        self.en(self.caisse)
        url = f"/api/api/tresorerie/reglements/{r['id']}/annuler/"
        self.assertEqual(self.client.post(url, {'motif': 'Erreur'}, format='json').status_code, 403)
        self.en(self.finances)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'motif': 'Mauvais montant saisi'}, format='json').status_code, 200)
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier, d.montant_paye), ('approuvee', 'a_payer', Decimal('0')))
        self.assertTrue(Reglement.objects.get(pk=r['id']).annule)

    def test_export_excel(self):
        self.approuver_frc()
        self.en(self.caisse)
        r = self.client.get('/api/api/tresorerie/a-payer/?export=xlsx')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'PK'))
        self.en(self.agent)
        self.assertEqual(self.client.get('/api/api/tresorerie/a-payer/').status_code, 403)


class AnnulationTests(TresorerieBase):
    def mission_approuvee(self):
        pk = self.creer_mission()
        self.soumettre(pk)
        return self.approuver(pk)

    def demander_annulation(self, parent, attendu=201):
        r = self.creer_type(self.ann, parent=parent, donnees={'motif': 'Mission reportée'}, objet='Annulation')
        self.assertEqual(r.status_code, attendu, r.data)
        return r.data

    def test_annulation_avant_paiement(self):
        mission = self.mission_approuvee()
        self.assertEqual(mission.statut, 'en_attente_cloture')  # mode B : la mission attend sa clôture
        self.en(self.agent)
        self.assertTrue(self.client.get(f'/api/api/demandes/{mission.pk}/').data['actions']['demander_annulation'])
        ann = self.demander_annulation(mission.pk)
        self.demander_annulation(mission.pk, attendu=400)  # une seule demande d'annulation en cours
        self.payer(mission.pk, '190000', attendu=400)    # paiement suspendu
        self.soumettre(ann['id'])
        d = self.approuver(ann['id'])
        self.assertEqual(d.statut, 'cloturee')  # sans montant : clôturée dès l'approbation
        mission.refresh_from_db()
        self.assertEqual((mission.statut, mission.statut_financier), ('annulee', 'sans_objet'))
        self.assertIn(d.reference, mission.motif_annulation)

    def test_annulation_apres_paiement_et_reversement(self):
        mission = self.mission_approuvee()
        self.payer(mission.pk, '190000')
        ann = self.demander_annulation(mission.pk)
        self.soumettre(ann['id'])
        self.approuver(ann['id'])
        mission.refresh_from_db()
        self.assertEqual((mission.statut, mission.statut_financier), ('annulee', 'reversement_attendu'))
        rev = Reversement.objects.get(demande=mission)
        self.assertEqual((rev.montant_du, rev.origine), (Decimal('190000'), 'annulation'))
        self.assertTrue(Notification.objects.filter(destinataire=self.agent, evenement='reversement').exists())
        self.en(self.caisse)
        self.assertEqual(self.client.get('/api/api/tresorerie/reversements/?etat=a_percevoir').data['count'], 1)
        r = self.client.post(f'/api/api/tresorerie/reversements/{rev.pk}/percevoir/', {'reference': 'ESP-12'},
                             format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        mission.refresh_from_db()
        self.assertEqual((mission.statut_financier, mission.montant_reverse), ('soldee', Decimal('190000')))

    def test_abandon_du_reversement(self):
        mission = self.mission_approuvee()
        self.payer(mission.pk, '190000')
        ann = self.demander_annulation(mission.pk)
        self.soumettre(ann['id'])
        self.approuver(ann['id'])
        rev = Reversement.objects.get(demande=mission)
        url = f'/api/api/tresorerie/reversements/{rev.pk}/abandonner/'
        self.en(self.caisse)
        self.assertEqual(self.client.post(url, {'motif': 'x'}, format='json').status_code, 403)
        self.en(self.finances)
        self.assertEqual(self.client.post(url, {'motif': 'Salarié parti, créance irrécouvrable'},
                                          format='json').status_code, 200)
        mission.refresh_from_db()
        self.assertEqual(mission.statut_financier, 'soldee')

    def test_parent_controle(self):
        brouillon = self.creer_mission()
        r = self.demander_annulation(brouillon, attendu=400)
        self.assertIn('demande_parent', r)
        self.en(self.agent)
        self.assertEqual(self.creer_type(self.ann, donnees={'motif': 'x'}).status_code, 400)  # parent obligatoire
        mission = self.mission_approuvee()
        self.en(self.autre)
        self.assertEqual(self.creer_type(self.ann, parent=mission.pk, user=self.autre,
                                         donnees={'motif': 'x'}).status_code, 403)
        self.en(self.agent)
        possibles = self.client.get(f'/api/api/demandes/parents-possibles/?type_demande={self.ann.pk}').data
        self.assertEqual([p['id'] for p in possibles], [mission.pk])


class ComplementsTests(TresorerieBase):
    def test_frais_complementaires_et_synthese(self):
        frc = self.approuver_frc()
        self.assertEqual(self.creer_type(self.fcm, parent=frc, montant='10000', donnees={'motif': 'x'}).status_code, 400)
        pk = self.creer_mission()
        self.soumettre(pk)
        mission = self.approuver(pk)
        r = self.creer_type(self.fcm, parent=mission.pk, montant='40000', donnees={'motif': 'Une nuit de plus'},
                            objet='Prolongation')
        self.assertEqual(r.status_code, 201, r.data)
        fcm = r.data['id']
        Demande.objects.get(pk=fcm).documents.create(fichier=fichier('facture.pdf'), nom_origine='facture.pdf',
                                                     taille=10, empreinte='x', ajoute_par=self.agent,
                                                     type_piece_id=self.fcm.exigences.get().type_piece_id)
        self.soumettre(fcm)
        self.approuver(fcm)
        self.payer(mission.pk, '190000')
        self.en(self.agent)
        detail = self.client.get(f'/api/api/demandes/{mission.pk}/').data
        s = detail['synthese']
        self.assertEqual((Decimal(s['engage_total']), Decimal(s['paye_total']), Decimal(s['solde_total'])),
                         (Decimal('230000'), Decimal('190000'), Decimal('40000')))
        self.assertEqual(detail['rattachees'][0]['type_code'], 'FCM')
        self.assertEqual(Demande.objects.get(pk=mission.pk).montant_approuve, Decimal('190000'))  # inchangé
        self.assertEqual(self.client.get(f'/api/api/demandes/{fcm}/').data['demande_parent_reference'],
                         mission.reference)


class PdfDemandeTests(TresorerieBase):
    def test_fiche_pdf(self):
        pk = self.creer_mission()
        self.soumettre(pk)
        self.approuver(pk)
        self.payer(pk, '100000')
        self.en(self.agent)
        r = self.client.get(f'/api/api/demandes/{pk}/pdf/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        self.assertTrue(r.content.startswith(b'%PDF'))
        self.assertIn('MLO-', r['Content-Disposition'])
        self.en(self.autre)
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/pdf/').status_code, 403)

    def test_ordre_de_mission_et_note_de_frais(self):
        from io import BytesIO
        from PIL import Image as Img
        from demandes.documents_mission import periode
        from datetime import date
        self.assertEqual(periode(date(2026, 7, 21), date(2026, 7, 25)), 'du 21 au 25 Juillet 2026')
        self.assertEqual(periode(date(2026, 7, 28), date(2026, 8, 2)), 'du 28 Juillet au 2 Août 2026')
        pk = self.creer_mission()
        self.soumettre(pk)
        self.en(self.agent)
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/ordre-mission/').status_code, 400)  # pas encore approuvée
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/note-frais/').status_code, 200)
        self.approuver(pk)
        self.en(self.agent)
        r = self.client.get(f'/api/api/demandes/{pk}/ordre-mission/')
        self.assertEqual((r.status_code, r['Content-Type']), (200, 'application/pdf'))
        frc = self.approuver_frc()
        self.en(self.agent)
        self.assertEqual(self.client.get(f'/api/api/demandes/{frc}/ordre-mission/').status_code, 400)
        # logo de la société (administrateur des finances)
        flux = BytesIO()
        Img.new('RGB', (120, 40), 'green').save(flux, 'PNG')
        flux.seek(0)
        flux.name = 'logo.png'
        self.en(self.finances)
        r = self.client.patch('/api/api/parametres-systeme/', {'logo': flux}, format='multipart')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['logo'])
        self.en(self.agent)
        self.assertEqual(self.client.get(f'/api/api/demandes/{pk}/ordre-mission/').status_code, 200)


class DecisionsTests(TresorerieBase):
    """Décisions du 24/11/2026 (docs/formation)."""

    def mission_soumise(self, **autres):
        pk = self.creer_mission(**autres)
        self.soumettre(pk)
        return pk

    def test_1_annulation_par_un_administrateur(self):
        pk = self.mission_soumise()
        admin = self.user('adm', groupes=('admin',))
        self.en(self.agent)
        self.assertFalse(self.client.get(f'/api/api/demandes/{pk}/').data['actions']['annuler_admin'])
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/annuler-admin/', {'motif': 'x'}, format='json').status_code, 403)
        self.en(admin)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/annuler-admin/', {}, format='json').status_code, 400)
        r = self.client.post(f'/api/api/demandes/{pk}/annuler-admin/', {'motif': 'Doublon de MLO-1'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data['statut'], 'annulee')
        self.assertFalse(Demande.objects.get(pk=pk).instances.filter(etat='en_cours').exists())
        self.assertIn("par l'administrateur", Demande.objects.get(pk=pk).actions.last().motif)

    def test_2_annulation_d_une_demande_cloturee(self):
        frc = self.approuver_frc()
        self.payer(frc, '500000')
        self.assertEqual(Demande.objects.get(pk=frc).statut, 'cloturee')
        r = self.creer_type(self.ann, parent=frc, donnees={'motif': 'Réception annulée, facture remboursée'}, objet='Annulation')
        self.assertEqual(r.status_code, 201, r.data)
        self.soumettre(r.data['id'])
        self.approuver(r.data['id'])
        d = Demande.objects.get(pk=frc)
        self.assertEqual((d.statut, d.statut_financier), ('annulee', 'reversement_attendu'))
        self.assertEqual(d.reversements.get().montant_du, Decimal('500000'))

    def test_4_pas_d_abandon_de_son_propre_reversement(self):
        self.agent.groups.add(*self.finances.groups.all())
        frc = self.approuver_frc()
        self.payer(frc, '500000')
        admin = self.user('adm', groupes=('admin',))
        self.en(admin).client.post(f'/api/api/demandes/{frc}/annuler-admin/', {'motif': 'Erreur'}, format='json')
        rev = Reversement.objects.get(demande_id=frc)
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/tresorerie/reversements/{rev.pk}/abandonner/', {'motif': 'x'},
                                          format='json').status_code, 403)

    def test_5_frais_complementaires_annules_avec_la_mission(self):
        pk = self.mission_soumise()
        self.approuver(pk)
        fcm = self.creer_type(self.fcm, parent=pk, montant='40000', donnees={'motif': 'Nuit'}, objet='Prolongation').data['id']
        Demande.objects.get(pk=fcm).documents.create(fichier=fichier('f.pdf'), nom_origine='f.pdf', taille=1, empreinte='x',
                                                     ajoute_par=self.agent, type_piece_id=self.fcm.exigences.get().type_piece_id)
        self.soumettre(fcm)
        self.approuver(fcm)
        self.payer(fcm, '40000')
        admin = self.user('adm', groupes=('admin',))
        self.en(admin).client.post(f'/api/api/demandes/{pk}/annuler-admin/', {'motif': 'Mission supprimée'}, format='json')
        f = Demande.objects.get(pk=fcm)
        self.assertEqual((f.statut, f.statut_financier), ('annulee', 'reversement_attendu'))

    def test_6_brouillons_des_autres_masques(self):
        brouillon = self.creer_mission()
        admin = self.user('adm', groupes=('admin',))
        self.en(admin)
        ids = [d['id'] for d in self.client.get('/api/api/demandes/?vue=toutes').data['results']]
        self.assertNotIn(brouillon, ids)

    def test_7_desactivation_bloquee_si_validations_en_attente(self):
        self.mission_soumise()
        admin = self.user('adm', groupes=('admin',))
        self.en(admin)
        r = self.client.patch(f'/api/api/users/{self.chef.pk}/', {'is_active': False}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('MLO-', str(r.data))
        self.assertTrue(type(self.chef).objects.get(pk=self.chef.pk).is_active)

    def test_8_et_9_chevauchement_et_regularisation(self):
        self.mission_soumise()
        pk = self.mission_soumise(depart_le='2026-12-03T08:00:00', retour_le='2026-12-05T18:00:00')
        codes = [a['code'] for a in Demande.objects.get(pk=pk).alertes]
        self.assertEqual(codes, ['chevauchement'])
        passe = self.mission_soumise(depart_le='2026-01-10T08:00:00', retour_le='2026-01-11T18:00:00')
        self.assertEqual([a['code'] for a in Demande.objects.get(pk=passe).alertes], ['regularisation'])

    def test_10_doublon_probable(self):
        self.soumettre(self.creer())
        pk = self.creer()
        d = self.soumettre(pk)
        self.assertEqual([a['code'] for a in d['alertes']], ['doublon'])

    def test_11_correction_du_montant_approuve_par_le_daf(self):
        frc = self.approuver_frc()
        url = f'/api/api/demandes/{frc}/corriger-montant/'
        self.en(self.agent)
        self.assertEqual(self.client.post(url, {'montant': '450000', 'motif': 'x'}, format='json').status_code, 403)
        self.en(self.daf)
        self.assertEqual(self.client.post(url, {'montant': '450000'}, format='json').status_code, 400)
        r = self.client.post(url, {'montant': '450000', 'motif': 'Facture définitive'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Decimal(r.data['montant_approuve']), Decimal('450000'))
        self.payer(frc, '200000', attendu=400)
        self.payer(frc, '450000')
        self.en(self.daf)
        self.assertEqual(self.client.post(url, {'montant': '400000', 'motif': 'x'}, format='json').status_code, 403)  # déjà payée
