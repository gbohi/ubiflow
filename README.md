# UbiFlow

Socle de la plateforme UbiFlow (demandes administratives et financières,
circuits de validation). Le dépôt ne contient pour l'instant que les
**paramètres** : utilisateurs, rôles, agences, départements, postes,
fonctions, catégories de salarié et statuts. Les modules métier viendront
s'y ajouter.

| Dossier    | Contenu                                                        |
|------------|----------------------------------------------------------------|
| `backend/` | API Django REST Framework + PostgreSQL, déployée avec Docker   |
| `web/`     | Back-office Angular 18                                         |
| `mobile/`  | Application Flutter (connexion, accueil, profil)               |
| `deploy/`  | Déploiement automatisé sur AWS EC2, sauvegardes                |
| `docs/`    | Dossier de conception (`docs/conception.md`)                   |

---

## ⚠️ Sécurité — historique Git

Ce dépôt reprend l'historique d'un ancien projet dont un fichier `.env` et
une clé API AllMySMS ont été publiés. Ne réutilisez **aucun** secret de cet
ancien projet : générez une nouvelle `SECRET_KEY` Django, un nouveau mot de
passe PostgreSQL et une nouvelle clé AllMySMS. Une purge de l'historique
(`git filter-repo`) reste recommandée.

---

## Rôles

Les rôles sont des groupes Django, créés par la migration
`api/migrations/0002_donnees_initiales.py` (avec les statuts « Actif » et
« Inactif ») :

| Rôle           | Droits |
|----------------|--------|
| `super_admin`  | Tout, y compris gérer les autres administrateurs et attribuer `super_admin` |
| `admin`        | Administration : utilisateurs, rôles, paramètres |
| `gestionnaire` | Consultation des paramètres (agences, organigramme) |
| `employe`      | Utilisateur standard : son profil, sa photo, son mot de passe |
| `admin_workflow`, `admin_finances`, `comptable`, `direction`, `controleur` | Rôles métier créés dès le lot 1, utilisés par les lots suivants |

Le backend applique ces règles sur chaque endpoint ; le web et le mobile
masquent en plus les écrans non autorisés.

## Paramètres

| Écran                  | API (`/api/api/…`)            | Modèle            |
|------------------------|-------------------------------|-------------------|
| Utilisateurs           | `users/`, `user-agences/`, `user-services/`, `user-postes/`, `user-categoriesalaries/` | `User` + affectations historisées |
| Rôles                  | `groups/`                     | `Group` (Django)  |
| Statuts                | `statuts/`                    | `Statut`          |
| Responsabilités        | `responsabilites/`, `affectations-responsabilite/` | `Responsabilite`, `AffectationResponsabilite` |
| N+1 (historique)       | `affectations-hierarchiques/`, `collaborateurs/{id}/reaffecter-n-plus-1/` | `AffectationHierarchique` |
| Véhicule personnel     | `situations-vehicule/`        | `SituationVehicule` |
| Situation à une date   | `collaborateurs/{id}/organisation/?date=`, `collaborateurs/moi/organisation/` | — |
| Organigramme           | `departements/arbre/?date=`   | — |
| Import Excel           | `imports-collaborateurs/` (+ `modele/`) | `ImportCollaborateurs` |
| Agences                | `agences/`                    | `Agence`          |
| Départements           | `services/`                   | `Service`         |
| Postes                 | `postes/`                     | `Poste` (département + fonction) |
| Fonctions              | `fonctions/`                  | `Fonction`        |
| Catégories de salarié  | `categoriesalaries/`          | `Categoriesalarie`|

Les règles d'organisation (N+1, titulaires, affectations à une date) sont
dans `backend/backend/api/organisation.py` ; l'import Excel dans
`api/import_collaborateurs.py`. Voir `docs/conception.md` (§3.1 et §17).

Chaque enregistrement garde ses dates et auteurs de création / modification
(`BaseModel`). Un élément de paramètre encore utilisé ne peut pas être
supprimé. Les affectations d'un agent sont historisées (date de début, date
de fin) ; un agent n'a qu'une agence et qu'une catégorie à la fois.

---

## Backend (Django)

### Développement local

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example backend/.env       # puis renseigner les valeurs (DB_HOST=localhost, DEBUG=True)
cd backend
python manage.py migrate
python manage.py createcachetable
python manage.py createsuperuser
python manage.py runserver
```

Tests : `python manage.py test api`

### Production (Docker)

```bash
cd backend
cp .env.example .env               # renseigner les valeurs
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser   # 1re fois
```

Le conteneur applique les migrations, crée la table de cache et collecte
les fichiers statiques à chaque démarrage.

> Le fichier `.env` se trouve désormais dans `backend/` (à côté de
> `docker-compose.yml`) et non plus dans `backend/backend/`.

### Déploiement automatisé sur AWS EC2

`deploy/aws/deploy.py` crée et configure tout le serveur depuis votre poste,
sans SSH : rôle IAM, groupe de sécurité (ports 80/443), IP élastique,
instance Ubuntu 24.04 (disque chiffré), secrets générés dans SSM Parameter
Store, Docker, PostgreSQL, Django, site Angular, compte `admin`,
sauvegarde quotidienne de la base.

1. Créer un utilisateur IAM avec la politique
   `deploy/aws/iam-politique-deploiement.json` et une clé d'accès.
2. ```bash
   pip install boto3
   export AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... AWS_DEFAULT_REGION=eu-north-1
   export UBIFLOW_ALLMYSMS_LOGIN=... UBIFLOW_ALLMYSMS_API_KEY=...   # optionnel
   python deploy/aws/deploy.py create
   ```
3. Mises à jour du code : `python deploy/aws/deploy.py update`

Le mot de passe du compte `admin` est dans AWS Console → Systems Manager →
Parameter Store → `/ubiflow/ADMIN_PASSWORD`. Console du serveur : EC2 →
instance « ubiflow » → Se connecter → Session Manager.

### Sauvegardes

Installées par `deploy/aws/server-setup.sh` (donc à chaque `deploy.py create`
ou `update`) :

- **Chaque nuit à 2 h** : la base PostgreSQL **et** les fichiers envoyés
  (photos de profil, documents) dans `/opt/ubiflow-backups/base` et `/opt/ubiflow-backups/fichiers`.
  Chaque sauvegarde de la base est vérifiée ; **14 jours** sont conservés.
- **Avant chaque mise à jour** (`deploy.py update`) : une sauvegarde
  « avant-deploiement ». Si elle échoue, le déploiement s'arrête.
- Journal : `/var/log/ubiflow-sauvegarde.log` (une ligne ❌ en cas d'échec).
- **Copie hors du serveur (recommandé)** : sans elle, la perte du disque
  emporte aussi les sauvegardes. Créer un bucket S3, autoriser le rôle de
  l'instance (`s3:PutObject` sur ce bucket), puis créer le paramètre SSM
  `/ubiflow/BACKUP_S3` = `s3://mon-bucket/ubiflow` et relancer `deploy.py update`.

Sauvegarde manuelle : `sudo bash /opt/ubiflow/deploy/aws/sauvegarde.sh manuelle`.

Restauration (remplace toutes les données ; l'état actuel est d'abord sauvegardé) :
```bash
sudo bash /opt/ubiflow/deploy/aws/restaurer.sh \
  /opt/ubiflow-backups/base/ubiflow_2026-10-20_0200_quotidienne.dump \
  /opt/ubiflow-backups/fichiers/media_2026-10-20_0200_quotidienne.tar.gz
```

### HTTPS (fortement recommandé)

Tant que l'API est en HTTP, mots de passe et jetons circulent en clair.

1. Faire pointer un nom de domaine (ex. `api.mondomaine.com`) vers le serveur.
2. Obtenir un certificat :
   ```bash
   docker run --rm -v /etc/letsencrypt:/etc/letsencrypt \
     -v "$PWD/nginx/certbot:/var/www/certbot" certbot/certbot certonly \
     --webroot -w /var/www/certbot -d api.mondomaine.com
   ```
3. Dans `nginx/nginx.conf` : décommenter le bloc `server { listen 443 … }`
   et la redirection HTTP → HTTPS.
4. Dans `.env` : `USE_HTTPS=True`, ajouter le domaine à `ALLOWED_HOSTS`,
   `CORS_ALLOWED_ORIGINS` et `CSRF_TRUSTED_ORIGINS`.
5. Mettre l'URL `https://` dans `web/src/environments/*.ts` et
   `mobile/lib/core/config.dart`, puis supprimer l'exception HTTP de
   `mobile/android/app/src/main/res/xml/network_security_config.xml`.

---

## Web (Angular)

```bash
cd web
npm ci
npm start                                   # développement
npx ng build --configuration production     # build → dist/
```

L'URL de l'API est dans `src/environments/environment*.ts`.

---

## Mobile (Flutter 3.22)

```bash
cd mobile
flutter pub get
flutter analyze
flutter test
flutter run
```

L'URL de l'API est dans `lib/core/config.dart`.

L'identifiant de l'application est `com.example.ubiflow` : à remplacer par
l'identifiant définitif avant une publication sur les stores. L'icône
(`assets/icons/app_icon.png`) est encore celle de l'ancien projet.
