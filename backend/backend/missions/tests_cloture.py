"""Lot 5 : clôture des missions (§9, mode B), dépenses réelles, reversement, note de frais réelle."""
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from demandes.models import Demande, TypePiece
from tresorerie.models import Reversement
from tresorerie.tests import TresorerieBase

DEPENSES = {'hotel': '45000', 'transport': '30000', 'telephone': '5000', 'divers': '0', 'reception': '0', 'detaxe': '0',
            'a_refacturer': '0'}


class ClotureTests(TresorerieBase):
    def mission_payee(self, montant='190000'):
        pk = self.creer_mission()
        self.soumettre(pk)
        self.approuver(pk)
        self.payer(pk, montant)
        return pk

    def joindre_rapport(self, pk):
        self.en(self.agent)
        r = self.client.post(f'/api/api/demandes/{pk}/documents/', {
            'fichier': SimpleUploadedFile('rapport.pdf', b'%PDF-1.4', content_type='application/pdf'),
            'type_piece': TypePiece.objects.get(code='rapport_mission').pk}, format='multipart')
        self.assertEqual(r.status_code, 201, r.data)

    def declarer(self, pk, depart='2026-12-01', retour='2026-12-03', depenses=None):
        self.en(self.agent)
        r = self.client.patch(f'/api/api/demandes/{pk}/cloture/', {'depart_reel': depart, 'retour_reel': retour,
                                                                    'depenses': depenses or DEPENSES,
                                                                    'observations': 'Audit réalisé.'}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_cloture_avec_reversement(self):
        pk = self.mission_payee()
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier), ('en_attente_cloture', 'payee'))
        c = self.declarer(pk)
        # 3 jours réels × 25 000 + 45 000 + 30 000 + 5 000 = 155 000 ; payé 190 000 → 35 000 à rembourser
        self.assertEqual((c['calcul']['jours'], c['calcul']['total'], c['calcul']['a_rembourser']), (3, '155000.00', '35000.00'))
        r = self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.assertEqual(r.status_code, 400)
        self.assertIn('documents', r.data)  # rapport de mission obligatoire
        self.joindre_rapport(pk)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/').status_code, 200)
        self.en(self.agent)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/valider/').status_code, 403)  # pas soi-même
        self.en(self.caisse)
        r = self.client.post(f'/api/api/demandes/{pk}/cloture/valider/')
        self.assertEqual(r.status_code, 200, r.data)
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.statut, d.statut_financier, d.montant_retenu), ('en_attente_cloture', 'reversement_attendu',
                                                                            Decimal('155000')))
        rev = Reversement.objects.get(demande=d)
        self.assertEqual((rev.montant_du, rev.origine), (Decimal('35000'), 'cloture'))
        self.client.post(f'/api/api/tresorerie/reversements/{rev.pk}/percevoir/', {}, format='multipart')
        d.refresh_from_db()
        self.assertEqual((d.statut, d.statut_financier), ('cloturee', 'soldee'))
        r = self.client.get(f'/api/api/demandes/{pk}/note-frais/')
        self.assertEqual(r.status_code, 200)

    def test_retour_par_le_controleur_et_reste_a_payer(self):
        pk = self.mission_payee('100000')  # partiellement payée
        self.joindre_rapport(pk)
        self.declarer(pk, depenses={**DEPENSES, 'hotel': '60000'})  # 75 000 + 60 000 + 30 000 + 5 000 = 170 000
        self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.en(self.caisse)
        self.assertEqual(self.client.get('/api/api/missions/clotures/').data[0]['id'], pk)
        self.assertEqual(self.client.post(f'/api/api/demandes/{pk}/cloture/retourner/', {}, format='json').status_code, 400)
        self.client.post(f'/api/api/demandes/{pk}/cloture/retourner/', {'motif': 'Joindre la facture d\'hôtel'}, format='json')
        self.declarer(pk, depenses={**DEPENSES, 'hotel': '60000'})  # le demandeur peut de nouveau modifier
        self.client.post(f'/api/api/demandes/{pk}/cloture/soumettre/')
        self.en(self.caisse)
        self.client.post(f'/api/api/demandes/{pk}/cloture/valider/')
        d = Demande.objects.get(pk=pk)
        self.assertEqual((d.montant_retenu, d.solde, d.statut_financier), (Decimal('170000'), Decimal('70000'),
                                                                           'partiellement_payee'))
        self.payer(pk, '80000', attendu=400)  # plus que le reste dû
        self.payer(pk, '70000')
        d.refresh_from_db()
        self.assertEqual((d.statut, d.statut_financier), ('cloturee', 'soldee'))

    def test_saisie_reservee_au_demandeur(self):
        pk = self.mission_payee()
        self.en(self.autre)
        self.assertEqual(self.client.patch(f'/api/api/demandes/{pk}/cloture/', {'observations': 'x'},
                                           format='json').status_code, 403)
