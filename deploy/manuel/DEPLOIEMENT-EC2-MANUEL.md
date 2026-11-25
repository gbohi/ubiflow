# Déploiement manuel d'UbiFlow sur une instance EC2 existante

Pour une instance EC2 **que vous avez créée vous-même** (ici `56.228.67.23`),
en **HTTP** (sans domaine ni HTTPS). L'outil `deploy/aws/deploy.py` ne convient
pas ici : il ne pilote que les instances qu'il a lui-même créées (via AWS SSM).
On déploie donc directement avec Docker.

> ⚠️ **En HTTP, les identifiants et les jetons circulent en clair.** Acceptable
> pour une démonstration sur données fictives ; **à ne pas utiliser avec de
> vraies données** RH ou financières. Passez à un domaine + HTTPS (dernière
> section) avant une mise en production réelle.

Prérequis : l'instance tourne sous **Ubuntu 22.04/24.04**, vous y accédez en SSH
(`ssh ubuntu@56.228.67.23`), et le **groupe de sécurité** autorise en entrée :
- **22/TCP** (SSH) — idéalement limité à votre IP,
- **80/TCP** (HTTP) — ouvert à `0.0.0.0/0` pour l'accès au site.

---

## 1. Installer Docker (une seule fois)

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 git
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu   # se reconnecter ensuite pour que ça prenne effet
```

Instance à **1 Go de RAM** (t3.micro…) : ajoutez 4 Go de swap, sinon le build
Angular échoue.

```bash
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 2. Récupérer le code (branche `main`, déjà à jour)

```bash
sudo mkdir -p /opt/ubiflow && sudo chown ubuntu:ubuntu /opt/ubiflow
git clone -b main https://github.com/gbohi/ubiflow.git /opt/ubiflow
cd /opt/ubiflow/backend
```

Dépôt privé : utilisez un *Personal Access Token* GitHub dans l'URL, ou une clé
de déploiement SSH.

## 3. Créer le fichier `backend/.env`

Génère des secrets solides et écrit le fichier. **Exécuter dans `/opt/ubiflow/backend`.**

```bash
cd /opt/ubiflow/backend
SECRET=$(python3 -c "import secrets;print(secrets.token_urlsafe(50))")
DBPASS=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
cat > .env <<EOF
SECRET_KEY=$SECRET
DEBUG=False
ALLOWED_HOSTS=56.228.67.23,localhost
USE_HTTPS=False

DB_NAME=ubiflow
DB_USER=ubiflow
DB_PASSWORD=$DBPASS
DB_HOST=db
DB_PORT=5432

CORS_ALLOWED_ORIGINS=http://56.228.67.23
CSRF_TRUSTED_ORIGINS=http://56.228.67.23
FRONTEND_URL=http://56.228.67.23

# SMS « mot de passe oublié » (optionnel : vide = pas d'envoi de SMS)
ALLMYSMS_LOGIN=
ALLMYSMS_API_KEY=
ALLMYSMS_SENDER=UbiFlow
EOF
chmod 600 .env
```

> `DEBUG=False` et `USE_HTTPS=False` sont volontaires : `False` pour le debug (jamais
> `True` en public), `False` pour HTTPS car on sert en HTTP tant qu'il n'y a pas de
> certificat (sinon Django redirigerait vers https:// et le site serait injoignable).

## 4. Construire et démarrer

```bash
cd /opt/ubiflow/backend
docker compose up -d --build
```

Le conteneur backend applique les migrations, crée la table de cache et collecte
les fichiers statiques automatiquement (voir `entrypoint.sh`). Le premier build
(Angular) prend plusieurs minutes.

Vérifier que l'API répond (401 attendu = elle tourne, authentification requise) :

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/api/api/users/me/   # → 401
docker compose ps
```

## 5. Créer le compte super administrateur

```bash
cd /opt/ubiflow/backend
docker compose exec backend python manage.py shell -c "
from django.contrib.auth.models import Group
from api.models import Statut, User
if not User.objects.filter(username='admin').exists():
    statut, _ = Statut.objects.get_or_create(libelle_statut='Actif')
    u = User.objects.create_superuser(username='admin', email='', password='CHANGEZ_MOI_UNE_FOIS!',
        nom='Administrateur', prenom='', contact='', poste_telephone='', statut=statut)
    u.groups.add(Group.objects.get(name='super_admin'))
    print('Compte admin créé.')
else:
    print('Compte admin déjà présent.')
"
```

Remplacez `CHANGEZ_MOI_UNE_FOIS!` par un mot de passe fort (≥ 8 car., 1 majuscule,
1 chiffre, 1 spécial), puis changez-le à la première connexion.

## 6. Vérifier

- Site : <http://56.228.67.23>
- API : <http://56.228.67.23/api/api/>
- Admin Django : <http://56.228.67.23/admin/>

Connexion : `admin` / le mot de passe choisi à l'étape 5.

---

## Mettre à jour (après un nouveau commit sur `main`)

```bash
cd /opt/ubiflow && git pull origin main
cd backend && docker compose up -d --build
```

## Journaux et dépannage

```bash
cd /opt/ubiflow/backend
docker compose logs --tail 100 backend     # erreurs Django
docker compose logs --tail 50 nginx        # accès / proxy
docker compose restart backend             # redémarrer l'API
```

## Sauvegarde de la base (à faire avant chaque mise à jour)

```bash
cd /opt/ubiflow/backend
docker compose exec -T db pg_dump -U ubiflow ubiflow | gzip > ~/ubiflow-$(date +%F).sql.gz
```

---

## Charte de sécurité minimale pour cette mise en ligne

Même en HTTP pour une démo, appliquez au moins :

1. **Groupe de sécurité** : n'ouvrez que 80 (et 22 limité à votre IP). Ne publiez
   jamais 5432 (PostgreSQL) — la compose ne l'expose pas, gardez-le ainsi.
2. **`/admin/`** : surface de force brute. Après la démo, restreignez-le (liste
   d'IP au niveau du groupe de sécurité ou du proxy).
3. **Mot de passe admin** fort et changé à la première connexion.
4. **Rappel** : HTTP = tout passe en clair. Voir le rapport d'audit
   (`docs/securite/`) et activer HTTPS dès qu'un domaine est disponible.

## Passer en HTTPS plus tard (recommandé avant la production)

1. Faire pointer un domaine (ex. `ubiflow.mondomaine.com`) vers `56.228.67.23`.
2. Installer le certificat Let's Encrypt (certbot via le webroot `nginx/certbot/`),
   décommenter le bloc `server { listen 443 ssl; … }` et la redirection
   HTTP → HTTPS dans `backend/nginx/nginx.conf`.
3. Dans `backend/.env` : `USE_HTTPS=True`, ajouter le domaine à `ALLOWED_HOSTS`,
   et aux origines CORS/CSRF en `https://`.
4. `docker compose up -d --build`.

Détails complets : `README.md`, section « HTTPS (fortement recommandé) ».

## Application mobile contre ce serveur (optionnel)

Pour tester l'app mobile sur ce backend HTTP :
- `mobile/lib/core/config.dart` → `serverUrl = 'http://56.228.67.23'` ;
- Android bloque le HTTP en clair : ajouter `56.228.67.23` dans
  `mobile/android/app/src/main/res/xml/network_security_config.xml`
  (bloc `domain-config cleartextTrafficPermitted="true"`).
  **À retirer** une fois le backend en HTTPS.
