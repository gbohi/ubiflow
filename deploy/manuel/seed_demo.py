"""
Jeu de collaborateurs de démonstration pour un test complet d'UbiFlow.

Crée (de façon idempotente) : 1 agence, 4 départements, 9 collaborateurs avec
leur rôle, leur catégorie, leur hiérarchie (N+1) et leurs responsabilités
(DG, DAF, chef comptable, responsables de département). Le circuit de validation
des missions — N+1 → DG → DAF → Visa du chef comptable — est donc complet.

À lancer sur le serveur, depuis backend/ :
    docker compose exec -T backend python manage.py shell < /opt/ubiflow/deploy/manuel/seed_demo.py

Relançable sans risque (ne recrée pas ce qui existe déjà).
Mot de passe commun : Demo@2026  (à changer après le test).
"""
from django.contrib.auth.models import Group
from django.utils import timezone

from api.models import (Agence, AffectationHierarchique, AffectationResponsabilite, Categoriesalarie, Responsabilite,
                        Service, Statut, User, UserAgence, UserCategoriesalarie, UserService)

MDP = 'Demo@2026'
actif = Statut.objects.get(libelle_statut='Actif')
aujourd = timezone.now()
cadre = Categoriesalarie.objects.get(libelle='Cadre')
noncadre = Categoriesalarie.objects.get(libelle='Non-cadre')

# ── Agence ───────────────────────────────────────────────────
agence, _ = Agence.objects.get_or_create(code='ABJ', defaults={'nom_agence': 'Abidjan'})

# ── Départements (parent → enfant) ───────────────────────────
def dep(libelle, code, parent=None):
    o, _ = Service.objects.get_or_create(code=code, defaults={'libelle_service': libelle, 'parent': parent})
    return o

dg   = dep('Direction générale', 'DG')
fin  = dep('Finances', 'FIN', dg)
cpt  = dep('Comptabilité', 'CPT', fin)
com  = dep('Commercial', 'COM', dg)

# ── Responsabilités (référence, déjà créées par migration) ───
R_DG   = Responsabilite.objects.get(code='DG')
R_DAF  = Responsabilite.objects.get(code='DAF')
R_CHEF = Responsabilite.objects.get(code='CHEF_COMPTABLE')
R_RESP = Responsabilite.objects.get(code='RESP_DEPARTEMENT')


def creer(matricule, nom, prenom, departement, categorie, roles=(), resp_globale=None, resp_departement=None):
    u, cree = User.objects.get_or_create(
        username=matricule,
        defaults=dict(nom=nom, prenom=prenom, email='', civilite='', contact='', poste_telephone='', statut=actif))
    if cree:
        u.set_password(MDP)
        u.save()
    for r in roles:
        u.groups.add(Group.objects.get(name=r))
    if not u.userservice_set.exists():
        UserService.objects.create(user=u, service=departement, date_debut=aujourd, statut=actif)
    if not u.usercategoriesalarie_set.exists():
        UserCategoriesalarie.objects.create(user=u, categoriesalarie=categorie, date_debut=aujourd, statut=actif)
    if not u.useragence_set.exists():
        UserAgence.objects.create(user=u, agence=agence, date_debut=aujourd, statut=actif)
    # Responsabilité à portée globale (DG, DAF, chef comptable)
    if resp_globale and not AffectationResponsabilite.objects.filter(user=u, responsabilite=resp_globale).exists():
        AffectationResponsabilite.objects.create(user=u, responsabilite=resp_globale, date_debut=aujourd.date())
    # Responsabilité de département (responsable → N+1 automatique de ses collègues)
    if resp_departement and not AffectationResponsabilite.objects.filter(
            user=u, responsabilite=R_RESP, departement=resp_departement).exists():
        AffectationResponsabilite.objects.create(user=u, responsabilite=R_RESP, departement=resp_departement,
                                                 date_debut=aujourd.date())
    return u


# ── Valideurs (responsables) ─────────────────────────────────
#  Chaque responsable de département devient le N+1 automatique de son équipe.
creer('DIR01', 'KOUADIO', 'Marc',   dg,  cadre, roles=('direction',),      resp_globale=R_DG,   resp_departement=dg)
creer('DAF01', 'BAMBA',   'Awa',    fin, cadre, roles=('admin_finances',), resp_globale=R_DAF,  resp_departement=fin)
creer('CPT01', 'YAO',     'Ange',   cpt, cadre, roles=(),                  resp_globale=R_CHEF, resp_departement=cpt)
creer('COM01', 'TRAORE',  'Seydou', com, cadre, roles=(),                  resp_departement=com)

# ── Comptable (enregistre les paiements) ─────────────────────
creer('CPT02', 'KONE', 'Fatou', cpt, noncadre, roles=('comptable',))

# ── Contrôleur (consultation, tableaux de bord et statistiques) ─
creer('CTRL01', 'KOFFI', 'Paul', dg, cadre, roles=('controleur',))

# ── Demandeurs (équipe commerciale : circuit à 4 valideurs distincts) ─
#  N+1 automatique = COM01 (responsable Commercial), puis DG, DAF, chef comptable.
creer('COM10', 'DIALLO',    'Ibrahim', com, cadre,    roles=())
creer('COM11', "N'GUESSAN", 'Marie',   com, noncadre, roles=())
creer('COM12', 'OUATTARA',  'Aicha',   com, cadre,    roles=())

print('\n=== Collaborateurs de démonstration ===')
print('Mot de passe commun :', MDP, '(à changer après le test)\n')
import api.organisation as org
for u in User.objects.exclude(username='admin').order_by('username'):
    deps = [x.service.libelle_service for x in u.userservice_set.all()]
    resp = [r.responsabilite.code + ('@' + r.departement.libelle_service if r.departement_id else '') for r in u.responsabilites.all()]
    roles = [g for g in u.groups.values_list('name', flat=True)]
    n1 = org.n_plus_1(u)
    print(f"{u.username:7} {u.nom} {u.prenom:9} | dép. {deps[0] if deps else '—':20} | "
          f"rôles {','.join(roles) or '—':16} | resp. {','.join(resp) or '—':28} | N+1 : {n1.responsable.username if n1.trouve else '—'}")
print('\nConnexion : matricule ci-dessus / mot de passe Demo@2026')
