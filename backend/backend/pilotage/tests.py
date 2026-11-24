"""Lot 6 : tableaux de bord par profil (§14) vérifiés sur un jeu de données de test."""
from decimal import Decimal

from tresorerie.tests import TresorerieBase


class TableauxDeBordTests(TresorerieBase):
    def jeu_de_donnees(self):
        """Mission payée 190 000, FRC approuvée 500 000 (à payer), FRC en validation 300 000."""
        mission = self.creer_mission()
        self.soumettre(mission)
        self.approuver(mission)
        self.payer(mission, '190000')
        frc = self.approuver_frc('500000')
        en_cours = self.creer(montant='300000', donnees={'date_reception': '2026-12-20', 'client': 'CIE',
                                                         'nombre_participants': 2, 'lieu': 'Plateau', 'justification': 'x'})
        self.soumettre(en_cours)
        return mission, frc, en_cours

    def tdb(self, user, profil, attendu=200, **filtres):
        self.en(user)
        r = self.client.get(f'/api/api/tableaux-de-bord/{profil}/', filtres)
        self.assertEqual(r.status_code, attendu, getattr(r, 'data', None))
        return r.data

    def indicateur(self, data, cle):
        return next(i['valeur'] for i in data['indicateurs'] if i['cle'] == cle)

    def section(self, data, cle):
        return next(s for s in data['sections'] if s['cle'] == cle)

    def test_acces_par_profil(self):
        self.en(self.agent)
        codes = [p['code'] for p in self.client.get('/api/api/tableaux-de-bord/').data]
        self.assertEqual(codes, ['collaborateur', 'valideur'])
        self.tdb(self.agent, 'direction', attendu=403)
        self.en(self.caisse)
        self.assertIn('comptabilite', [p['code'] for p in self.client.get('/api/api/tableaux-de-bord/').data])

    def test_collaborateur(self):
        self.jeu_de_donnees()
        d = self.tdb(self.agent, 'collaborateur')
        self.assertEqual(self.indicateur(d, 'soumises'), 3)
        self.assertEqual(self.indicateur(d, 'en_validation'), 1)
        self.assertEqual(self.indicateur(d, 'a_cloturer'), 1)
        self.assertEqual(Decimal(self.indicateur(d, 'approuve')), Decimal('690000'))
        self.assertEqual(Decimal(self.indicateur(d, 'paye')), Decimal('190000'))
        self.assertEqual(len(self.section(d, 'missions')['lignes']), 1)

    def test_direction(self):
        self.jeu_de_donnees()
        admin = self.user('adm', groupes=('admin',))
        d = self.tdb(admin, 'direction')
        self.assertEqual((self.indicateur(d, 'soumises'), self.indicateur(d, 'missions'), self.indicateur(d, 'locales')), (3, 1, 1))
        self.assertEqual(Decimal(self.indicateur(d, 'demande')), Decimal('990000'))
        self.assertEqual(Decimal(self.indicateur(d, 'engagements')), Decimal('500000'))  # FRC approuvée non payée
        par_type = {l['libelle']: Decimal(l['valeur']) for l in self.section(d, 'par_type')['donnees']}
        self.assertEqual(par_type, {'Frais de réception client': Decimal('500000'), 'Mission locale': Decimal('190000')})
        mensuel = self.section(d, 'mensuel')
        self.assertEqual(sum(Decimal(m['valeurs']['paye']) for m in mensuel['donnees']), Decimal('190000'))
        # filtre par type : seulement les FRC
        d = self.tdb(admin, 'direction', type_demande=self.frc.pk)
        self.assertEqual(self.indicateur(d, 'soumises'), 2)
        # période sans demande
        d = self.tdb(admin, 'direction', du='2020-01-01', au='2020-12-31')
        self.assertEqual(self.indicateur(d, 'soumises'), 0)

    def test_comptabilite_et_valideur(self):
        self.jeu_de_donnees()
        d = self.tdb(self.caisse, 'comptabilite')
        self.assertEqual(self.indicateur(d, 'a_payer'), 1)
        self.assertEqual(Decimal(self.indicateur(d, 'reste')), Decimal('500000'))
        self.assertEqual(Decimal(self.indicateur(d, 'paye')), Decimal('190000'))
        self.assertEqual(self.section(d, 'par_mode')['donnees'][0]['libelle'], 'Virement')
        v = self.tdb(self.chef, 'valideur')
        self.assertEqual(self.indicateur(v, 'a_traiter'), 1)  # FRC en validation chez le N+1
        self.assertEqual(self.indicateur(v, 'traitees'), 2)
        self.assertEqual(len(self.section(v, 'historique')['lignes']), 2)

    def test_administrateur(self):
        admin = self.user('adm', groupes=('admin',))
        d = self.tdb(admin, 'administrateur')
        self.assertGreaterEqual(self.indicateur(d, 'circuits'), 7)
        self.assertGreaterEqual(self.indicateur(d, 'actifs'), 6)
