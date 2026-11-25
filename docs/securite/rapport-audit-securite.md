---
title: "UbiFlow — Audit de sécurité applicative"
subtitle: "Test d'intrusion en boîte blanche (web + mobile) — Rapport de soutenance"
date: "25 novembre 2026"
---

# Présentation du projet de soutenance

**Sujet.** Évaluer la sécurité de l'application UbiFlow (gestion des demandes
de mission, de paiement et de remboursement) et déterminer si elle est
« piratable » : vol de données, usurpation de compte, élévation de privilèges,
injection. L'étude porte sur les trois composants : l'API Django/DRF, le client
web Angular et l'application mobile Flutter.

**Méthode.** Revue de code en boîte blanche (accès complet au dépôt), inspirée de
l'**OWASP ASVS** et du **Top 10 OWASP 2021**, complétée par des essais ciblés
sur l'application en fonctionnement (comptes de démonstration des cinq profils).

**Équipe et répartition.**

| Intervenant | Cursus | Périmètre présenté |
|---|---|---|
| **A. — Carnegie Mellon University (CMU)** | Réseaux & sécurité des systèmes | Transport, infrastructure, configuration serveur, anti-force brute, exposition |
| **B. — Georgia Institute of Technology** | Sécurité applicative | Authentification, autorisations/IDOR, injection, cycle de vie des jetons, téléversements |
| **C. — University of Oxford** | Développement d'applications | Clients web et mobile : stockage des jetons, XSS/CSP, TLS mobile, durcissement |

**Verdict global.** Aucune vulnérabilité **critique** directement exploitable
n'a été trouvée. L'architecture applique déjà de bonnes pratiques (ORM partout,
contrôle d'accès objet par objet, OTP à comparaison constante, stockage mobile
chiffré, secrets non commités). Les constats sont des points de **durcissement**
à traiter **avant la mise en production**, classés ci-dessous Important / Moyen /
Faible. Aucun n'empêche le fonctionnement ; plusieurs sont des réglages de
déploiement.

\newpage

# Intervenant A (CMU) — Réseau, infrastructure et exposition

## Ce que j'ai testé
Chiffrement du transport, configuration Django de production, politique CORS/CSRF,
résistance à la force brute, surface d'exposition (admin, fichiers média, secrets).

## Points forts constatés
- **Secrets non commités** : `.env` ignoré par git, `.env.example` sans valeurs,
  `SECRET_KEY` sans valeur par défaut (l'application refuse de démarrer sans clé).
- `DEBUG=False` par défaut ; `SECURE_CONTENT_TYPE_NOSNIFF`, `X_FRAME_OPTIONS=DENY`,
  `SECURE_PROXY_SSL_HEADER`, redirection HTTPS et cookies `Secure` pilotés par
  `USE_HTTPS` ; HSTS activé en HTTPS.
- **CORS** restreint par liste blanche en production (`CORS_ALLOWED_ORIGINS`).
- **CSRF** peu pertinent pour l'API : l'authentification se fait par jeton JWT
  dans l'en-tête `Authorization`, pas par cookie de session.

## Constats et pistes d'attaque

### A1 — Transport non chiffré par défaut (mobile) · **Important**
`mobile/lib/core/config.dart` pointe par défaut sur `http://10.0.2.2:8000`
(boucle locale de l'émulateur). Livré tel quel, le mobile enverrait le JWT en
clair → **interception (MITM) et vol de jeton** sur un réseau Wi-Fi hostile.
*Atténuation déjà présente :* `network_security_config.xml` bloque le trafic en
clair pour tout domaine **sauf** `10.0.2.2`, et iOS n'a aucune exception ATS.
**Correctif :** en production, URL `https://` et suppression du bloc `10.0.2.2` ;
vérifier qu'aucun `cleartextTrafficPermitted="true"` ne subsiste.

### A2 — Anti-force brute insuffisant · **Important**
La connexion est limitée à `20/min` **par adresse IP** (`ScopedRateThrottle`),
sans **blocage au niveau du compte**. Un attaquant distribué (botnet, rotation
d'IP) peut mener du *credential stuffing*. De plus l'administration Django
(`/admin/`) utilise la session Django et **n'est pas couverte** par cette limite.
**Correctifs :** intégrer **django-axes** (blocage après N échecs par compte +
IP), restreindre `/admin/` (VPN / liste d'IP / renommage), et définir `NUM_PROXIES`
(ou un `X-Forwarded-For` de confiance) pour que la limite s'applique à la **vraie**
IP cliente derrière le reverse-proxy, et non à celle du proxy.

### A3 — Service des fichiers média en production · **Moyen**
Les pièces jointes (justificatifs, documents financiers) sont servies par la
route **authentifiée** `/demandes/{id}/documents/{doc}/fichier/` (bon). Mais
`MEDIA_ROOT` contient les fichiers en clair ; si le reverse-proxy expose
`/media/` en statique, **toute personne connaissant l'URL** y accède sans
authentification. Les noms sont des UUID aléatoires (non devinables), ce qui
limite le risque, mais ce n'est pas un contrôle d'accès.
**Correctif :** ne jamais exposer `/media/` publiquement ; servir via l'endpoint
authentifié (ou `X-Accel-Redirect`/`sendfile` derrière le contrôle de droits).

### A4 — En-têtes de sécurité au niveau du proxy · **Faible**
Ajouter au reverse-proxy : `Referrer-Policy`, `Permissions-Policy`, et confirmer
HSTS (`includeSubDomains; preload`) une fois le HTTPS stable.

\newpage

# Intervenant B (Georgia Tech) — Sécurité applicative (API)

## Ce que j'ai testé
Authentification, autorisations et **IDOR** (accès à l'objet d'un autre
utilisateur), injection SQL, cycle de vie des jetons JWT, parcours « mot de passe
oublié » (OTP), élévation de privilèges, téléversement de fichiers.

## Points forts constatés
- **Aucune injection SQL** : tout passe par l'ORM Django. Aucune trace de `.raw()`,
  `.extra()`, `cursor.execute`, `eval`, `exec`, `mark_safe`, `pickle`,
  `os.system`/`subprocess`.
- **IDOR bien bloqué** : la lecture d'une demande passe par `peut_voir(demande, user)`
  (demandeur, créateur, valideur, ou rôle de gestion **dans son périmètre**) ; les
  listes sont filtrées par `demandes_visibles(user)` ; le téléchargement d'une
  pièce vérifie `get_object_or_404(Document, pk=doc, demande=demande)` — impossible
  de récupérer la pièce d'une demande qu'on n'a pas le droit de voir.
- **Élévation de privilèges verrouillée** : toute écriture sur les comptes exige
  `IsAdminRole` ; `validate_groups` interdit d'attribuer `super_admin` sans l'être ;
  `/users/me/` est en **lecture seule** ; `is_superuser` est `read_only` ; garde-fous
  empêchant un administrateur de se retirer ses propres droits ou de se désactiver.
- **OTP robuste** : code à 6 chiffres via `secrets`, comparaison à **temps constant**
  (`hmac.compare_digest`), **5 essais** puis invalidation, **3 demandes / 30 min / matricule**,
  **pas d'énumération** de comptes (message identique que le compte existe ou non),
  jeton de réinitialisation à usage unique.
- **Téléversements** : liste blanche d'extensions, taille maximale (paramétrable),
  nom de stockage aléatoire (UUID), empreinte SHA-256, envoi en pièce jointe
  (`as_attachment`) — pas d'exécution dans le navigateur ; SVG **non** autorisé
  (évite le XSS stocké par image).

## Constats et pistes d'attaque

### B1 — Les jetons survivent au changement de mot de passe · **Important**
`SIMPLE_JWT` n'active ni `ROTATE_REFRESH_TOKENS` ni `BLACKLIST_AFTER_ROTATION`.
Le `reset-password` et le changement de mot de passe **ne révoquent pas** les
jetons déjà émis. Conséquence : si une session a été volée (ou simplement restée
ouverte sur un poste), **réinitialiser le mot de passe ne la coupe pas** — le
jeton d'accès reste valide jusqu'à 1 h et le *refresh* jusqu'à 1 jour.
**Correctifs :** activer la rotation + liste noire après rotation ; à chaque
changement/réinitialisation de mot de passe, **blacklister les jetons** de
l'utilisateur (parcours `OutstandingToken`) ; réduire éventuellement la durée du
*refresh*.

### B2 — Validation de fichier par extension seulement · **Moyen**
Le type est jugé sur l'**extension**, pas sur le contenu réel (nombres magiques).
Un fichier malveillant renommé `.pdf` passe le filtre (il n'est pas exécuté côté
serveur, mais peut viser le poste qui l'ouvrira).
**Correctif :** vérifier le type MIME réel (p. ex. `python-magic`) et le cohérer
avec l'extension ; conserver l'envoi en pièce jointe + `Content-Disposition`.

### B3 — Journalisation et séparation des privilèges · **Faible (constat positif à maintenir)**
Le journal d'activité trace les opérations sensibles (paramétrage, barèmes,
réaffectations, retraits de pièces). Recommandation : y ajouter les **échecs de
connexion** et les **réinitialisations de mot de passe** pour la détection
d'intrusion, et s'assurer que ces journaux sont exportés hors du serveur.

\newpage

# Intervenant C (Oxford) — Clients web et mobile

## Ce que j'ai testé
Stockage des jetons, exposition au **XSS** et politique **CSP**, fuite de jeton
par l'intercepteur, stockage des secrets sur mobile, TLS mobile, liens profonds,
journaux.

## Points forts constatés
- **Web** : aucune utilisation de `bypassSecurityTrust`, `[innerHTML]` lié à des
  données, `eval` ou `document.write`. Le seul `innerHTML` écrit une constante
  (« Enregistrer »). Angular échappe le HTML par défaut → surface XSS faible.
- **Mobile** : les jetons sont dans **`flutter_secure_storage`**
  (Keychain iOS / Keystore Android), pas dans `SharedPreferences`. `SharedPreferences`
  ne sert qu'au thème et au « se souvenir du matricule » (jamais le mot de passe).
- **Aucun contournement TLS** mobile (pas de `badCertificateCallback`), **aucun
  secret journalisé**, **aucun lien profond** personnalisé (pas de détournement
  d'intent), **aucun secret Firebase/Google** commité.

## Constats et pistes d'attaque

### C1 — Jetons JWT en `localStorage` + absence de CSP · **Important**
Le client web stocke l'`access` **et** le `refresh` dans `localStorage`, lisible
par **tout JavaScript** de la page. Il n'y a **aucune** politique `Content-Security-Policy`.
Aujourd'hui la surface XSS est faible, mais **si** une faille XSS était introduite
(dépendance, futur composant), l'attaquant **exfiltrerait les deux jetons** et
prendrait le contrôle du compte.
**Correctifs :** (1) déployer une **CSP** stricte (proxy ou `meta`) :
`default-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'` ;
(2) idéalement migrer le *refresh* vers un **cookie `HttpOnly` + `Secure` + `SameSite=Strict`**
(hors de portée du JS) ; (3) maintenir la discipline anti-XSS et le scan de
dépendances.

### C2 — L'intercepteur ajoute le jeton à toutes les requêtes · **Moyen**
`auth.interceptor.ts` ajoute `Authorization: Bearer …` à **chaque** requête
sortante sans filtrer le domaine. Toutes les requêtes visent aujourd'hui l'API,
mais une future requête vers un tiers (CDN, service externe) **enverrait le jeton**
à ce tiers.
**Correctif :** n'attacher le jeton qu'aux URL de l'API (préfixe `environment.apiUrl`).

### C3 — Durcissement mobile · **Faible**
- Expliciter `AndroidOptions(encryptedSharedPreferences: true)` pour
  `flutter_secure_storage`.
- Envisager l'**épinglage de certificat** (certificate pinning) et une
  **détection root/jailbreak** pour les données financières.
- `android:exported="true"` sur `MainActivity` est **normal** (filtre LAUNCHER
  uniquement) ; aucun autre composant exporté — pas d'action requise.

\newpage

# Synthèse des constats

| Réf | Constat | Composant | Criticité | OWASP | Correctif |
|---|---|---|---|---|---|
| A1 | HTTP en clair par défaut (mobile) | Mobile/Infra | Important | A02 | URL `https://` en prod, retirer l'exception cleartext |
| A2 | Anti-force brute faible, `/admin` non limité | API/Infra | Important | A07 | django-axes, `NUM_PROXIES`, restreindre `/admin` |
| B1 | Jetons non révoqués au reset mot de passe | API | Important | A07 | Rotation + blacklist, révoquer à la MAJ du mot de passe |
| C1 | JWT en `localStorage`, pas de CSP | Web | Important | A05/A03 | CSP stricte, refresh en cookie HttpOnly |
| A3 | `/media` exposable sans auth | Infra | Moyen | A01 | Servir via endpoint authentifié / X-Accel |
| B2 | Validation de fichier par extension | API | Moyen | A08 | Vérifier le type MIME réel |
| C2 | Jeton envoyé à tous les domaines | Web | Moyen | A07 | Filtrer sur l'origine de l'API |
| A4 | En-têtes proxy à compléter | Infra | Faible | A05 | Referrer-Policy, Permissions-Policy, HSTS |
| B3 | Journaliser échecs de connexion / resets | API | Faible | A09 | Étendre le journal, export externe |
| C3 | Durcissement mobile (pinning, root) | Mobile | Faible | — | Options Android explicites, pinning, anti-root |

## Ce qui est déjà solide (à préserver)
Pas d'injection SQL (ORM), IDOR bloqué objet par objet, élévation de privilèges
verrouillée, OTP à temps constant sans énumération, stockage mobile chiffré, pas
de contournement TLS, secrets non commités, `DEBUG=False` par défaut.

# Recommandations transverses (CI/CD)
- **Analyse de dépendances** en continu : `pip-audit`, `npm audit`,
  `flutter pub outdated` dans l'intégration continue.
- **SAST** : `bandit` (Python), `semgrep`, `npm`/ESLint sécurité.
- **Secrets scanning** (gitleaks) sur chaque *push*.
- Rejouer cet audit avant chaque mise en production majeure.

# Conclusion
UbiFlow résiste aux attaques classiques testées (injection, IDOR, usurpation,
élévation de privilèges). Les points **Importants** (B1, C1, A1, A2) relèvent du
durcissement et du déploiement et doivent être traités **avant la mise en
production** ; ils sont tous corrigeables sans refonte. L'application est **saine
dans sa conception** ; l'enjeu restant est la **rigueur de déploiement** et
quelques réglages de robustesse.
