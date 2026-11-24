"""Lot 6 : tableaux de bord par profil (§14) vérifiés sur un jeu de données de test."""
from decimal import Decimal

from tresorerie.tests import TresorerieBase


class JeuDeDonnees(TresorerieBase):
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


class TableauxDeBordTests(JeuDeDonnees):

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


class AccueilTests(JeuDeDonnees):
    def accueil(self, user, **params):
        self.en(user)
        r = self.client.get('/api/api/accueil/', params)
        self.assertEqual(r.status_code, 200, getattr(r, 'data', None))
        return r.data

    def kpi(self, data, cle):
        return next(k['valeur'] for k in data['kpis'] if k['cle'] == cle)

    def test_accueil_par_profil(self):
        self.jeu_de_donnees()
        d = self.accueil(self.agent)
        self.assertEqual(d['profil'], 'collaborateur')
        self.assertEqual((self.kpi(d, 'toutes'), self.kpi(d, 'en_cours'), self.kpi(d, 'approuvees'), self.kpi(d, 'actions')), (3, 1, 2, 1))
        # « À faire » : la mission à clôturer, avec son action
        self.assertEqual([(e['motif'], e['action']) for e in d['a_faire']], [('a_cloturer', 'Déclarer mes dépenses')])
        self.assertEqual(d['resume'], '1 demande attend une action de votre part')
        v = self.accueil(self.chef)
        self.assertEqual(v['profil'], 'valideur')
        self.assertEqual(self.kpi(v, 'a_valider'), 1)
        self.assertEqual([e['motif'] for e in v['a_faire']], ['a_valider'])
        f = self.accueil(self.caisse)
        self.assertEqual(f['profil'], 'finances')
        self.assertEqual(Decimal(self.kpi(f, 'attente')), Decimal('500000'))
        a_payer = [e for e in f['a_faire'] if e['motif'] == 'a_payer']
        self.assertEqual((len(a_payer), a_payer[0]['type_code'], a_payer[0]['action']), (1, 'FRC', 'Payer'))
        self.assertTrue(f['activites'] is not None)
        admin = self.user('adm', groupes=('admin',))
        g = self.accueil(admin)
        self.assertEqual(g['profil'], 'direction')
        self.assertEqual((self.kpi(g, 'total'), Decimal(self.kpi(g, 'budget'))), (3, Decimal('690000')))
        self.assertEqual({x['libelle'] for x in g['graphes'][0]['donnees']}, {'Missions locales', 'Réceptions client'})
        # profil demandé explicitement
        self.assertEqual(self.accueil(admin, profil='collaborateur')['profil'], 'collaborateur')
        self.assertEqual(self.accueil(self.agent, profil='direction')['profil'], 'collaborateur')  # non autorisé


class AnnuaireTests(JeuDeDonnees):
    def test_annuaire_ouvert_a_un_employe(self):
        u = self.user('ann1')
        self.client.force_authenticate(u)
        r = self.client.get('/api/api/annuaire/', {'q': 'ann1'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data and set(r.data[0]) == {'id', 'matricule', 'nom', 'prenom', 'libelle'})


class RechercheTests(JeuDeDonnees):
    def chercher(self, user, q):
        self.en(user)
        r = self.client.get('/api/api/recherche/', {'q': q})
        self.assertEqual(r.status_code, 200)
        return r.data

    def test_recherche_limitee_aux_demandes_visibles(self):
        self.jeu_de_donnees()
        mes = self.chercher(self.agent, self.agent.nom)
        self.assertGreaterEqual(mes['total'], 1)
        self.assertTrue(all(d['demandeur'].startswith(self.agent.nom) for d in mes['demandes']))
        # un autre employé, sans rôle ni validation, ne voit pas les demandes de l'agent
        intrus = self.user('intrus')
        self.assertEqual(self.chercher(intrus, self.agent.nom)['total'], 0)
        # recherche par référence, et requête trop courte
        ref = mes['demandes'][0]['reference']
        self.assertEqual(self.chercher(self.agent, ref)['demandes'][0]['reference'], ref)
        self.assertEqual(self.chercher(self.agent, 'a')['total'], 0)


class FiltreFamilleTests(JeuDeDonnees):
    def test_liste_limitee_aux_missions(self):
        self.jeu_de_donnees()
        self.en(self.agent)
        r = self.client.get('/api/api/demandes/', {'famille': 'mission'})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data['results'])
        self.assertTrue(all(d['type_code'] in ('MLO', 'MHP') for d in r.data['results']))
        d = self.client.get('/api/api/accueil/', {'profil': 'collaborateur'}).data
        prochaines = next(l for l in d['listes'] if l['cle'] == 'prochaines')
        self.assertEqual(prochaines['lien_tout'], '/demandes?famille=mission')
        self.assertIn('Mission locale', [a['libelle'] for a in d['actions_rapides']])
