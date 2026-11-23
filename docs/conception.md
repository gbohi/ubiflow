# UbiFlow — Dossier de conception fonctionnelle et technique

Version 1.1 — référence pour le développement. Toute évolution de règle
métier doit d'abord être reportée dans ce document.

---

## 0. Objet et décisions validées

UbiFlow digitalise les demandes administratives et financières de
l'entreprise : missions locales, missions hors pays, frais de réception
client, demandes de paiement, demandes de remboursement et frais
complémentaires de mission. Elle couvre la soumission, la validation, le
paiement et la clôture, sur le web et le mobile, avec une API unique.

### Décisions validées

| # | Sujet | Décision |
|---|---|---|
| D1 | Per diem | Montant **et devise** paramétrables par type de mission et catégorie, avec date d'effet |
| D2 | Nombre de jours | `date de retour − date de départ + 1`, jours calendaires, **aucune demi-journée** |
| D3 | Transport avec véhicule | `distance retenue × tarif kilométrique` (aller simple ou aller-retour) |
| D4 | Transport sans véhicule | **Tarif par ville** de destination, aller-retour inclus, **identique pour toutes les catégories** |
| D5 | Dépenses réelles < montant payé | **Reversement** obligatoire à la clôture |
| D6 | Mission collective | Hors périmètre actuel : une demande = un missionnaire (modèle extensible) |
| D7 | Demandeur valideur de sa propre étape | Paramétrable par étape : validation **manuelle** ou **automatique** (et options « sauter » / « remonter ») |
| D8 | Même personne à deux étapes | Paramétrable par étape |
| D9 | Séparation approbation / paiement | Paramétrable par type de demande |
| D10 | Paiements fractionnés | Autorisés, **paramétrables par type de demande** |
| D11 | Budgets | Aucun contrôle budgétaire ; les « engagements » sont du reporting |
| D12 | Agences | Information de rattachement du salarié, copiée dans la demande, utilisée en reporting |
| D13 | E-mail | SMTP de l'entreprise, configuré plus tard (canal prévu, désactivable) |
| D14 | Push mobile | Firebase Cloud Messaging |
| D15 | Synchronisation RH | Import Excel ; le matricule est la clé de rapprochement |
| D16 | Transport mission hors pays | **Forfait fixe** (trajet vers l'aéroport), 20 000 par défaut, paramétrable (barème daté) et ajustable sur la demande avec justification |
| D17 | Devise de référence | **Paramétrable** (paramètre système) ; elle sert aux totaux, aux conversions et au reporting |

### Hypothèses (à confirmer si besoin)

- H1 — Les tarifs transport par ville concernent uniquement les **missions
  locales** ; une mission hors pays utilise le forfait aéroport (D16), le
  billet d'avion étant saisi en frais aérien.
- H2 — Le référentiel des villes est géré dans l'application (pas de
  service externe de géolocalisation).

---

## 1. Glossaire

| Terme | Définition |
|---|---|
| **Collaborateur** | Salarié, utilisateur de l'application (modèle `User`) |
| **Matricule** | Identifiant RH unique du collaborateur ; sert d'identifiant de connexion |
| **Département** | Unité organisationnelle (modèle technique `Service`), hiérarchisée |
| **Fonction / Poste** | Emploi RH du collaborateur (comptable, commercial…) |
| **Responsabilité** | Rôle tenu dans les circuits (DG, DAF, Chef comptable, Responsable de département…), daté, avec périmètre éventuel |
| **N+1** | Responsable hiérarchique du collaborateur à une date donnée |
| **Type de demande** | Catégorie de demande (mission locale, paiement…) avec son formulaire, son workflow et ses règles |
| **Workflow** | Circuit de validation d'un type de demande ; versionné |
| **Étape** | Maillon du workflow, avec ses valideurs, sa condition et ses règles |
| **Plan de validation** | Liste des étapes et valideurs calculée pour une demande donnée |
| **Tâche** | Action attendue d'un valideur sur une demande à une étape |
| **Délégation** | Transfert temporaire des validations d'un collaborateur à un autre |
| **Barème** | Paramètre financier daté : per diem, tarif kilométrique, tarif par ville, taux de change |
| **Figer** | Copier dans la demande la valeur applicable au moment de la soumission |
| **Règlement** | Paiement enregistré par la comptabilité (un ou plusieurs par demande) |
| **Reversement** | Somme due par le demandeur lorsque ses dépenses réelles sont inférieures au montant payé |

---

## 2. Architecture

### 2.1 Pile technique (inchangée)

- **Backend** : Django 5 + Django REST Framework, PostgreSQL, JWT
  (simplejwt). Toutes les règles métier sont exécutées côté serveur.
- **Web** : Angular 18 (back-office complet).
- **Mobile** : Flutter (Android, iOS), même API.
- **Tâches planifiées** : commande Django lancée périodiquement par un
  conteneur dédié (rappels, escalades, délégations expirées, purge).
  Passage à Celery + Redis seulement si la charge le justifie.
- **Fichiers** : stockage disque du serveur (volume Docker) au départ,
  abstrait par le système de stockage Django pour passer à S3 sans
  changement de code.
- **Notifications** : application (base de données), push (Firebase),
  e-mail (SMTP, activable).

### 2.2 Découpage en applications Django

| Application | Contenu |
|---|---|
| `organisation` | Collaborateurs (données étendues), départements, agences, fonctions, postes, responsabilités, affectations hiérarchiques, import Excel |
| `habilitations` | Rôles applicatifs, permissions, périmètres de consultation |
| `workflow` | Modèles de workflow, versions, étapes, règles, conditions, instances, tâches, actions, délégations |
| `demandes` | Socle générique : types de demande, demandes, versions de contenu, champs paramétrables, commentaires, numérotation |
| `missions` | Détail mission, calcul des frais, villes, distances |
| `baremes` | Per diem, tarifs kilométriques, tarifs par ville, devises et taux de change |
| `tresorerie` | File à payer, règlements, reversements |
| `documents` | Pièces jointes, types de pièces, exigences, historique, conservation |
| `notifications` | Événements, modèles de messages, canaux, préférences, rappels |
| `audit` | Journal d'activité en ajout seul |
| `reporting` | Tableaux de bord, statistiques, exports |

Les dépendances vont toujours du métier vers le socle :
`missions → demandes → workflow → organisation`. Le moteur de workflow ne
connaît aucun type de demande particulier : il manipule une demande
générique et lit ses données au travers d'une interface (`valeurs pour
conditions`, `champs sensibles`).

### 2.3 Principes transverses

1. **Pas de circuit dans le code** : tout circuit est une donnée.
2. **Tout ce qui est daté est historisé** (affectations, responsabilités,
   barèmes) : jamais d'écrasement, une nouvelle ligne avec date d'effet.
3. **Figer à la soumission** : la demande garde la version du workflow,
   le N+1, l'organisation du demandeur et les barèmes appliqués.
4. **Aucune suppression physique** d'une donnée engagée (demande soumise,
   action, pièce, règlement) ; annulation ou remplacement tracés.
5. **Service métier unique** : les vues API, le web et le mobile passent
   tous par les mêmes services (`soumettre`, `approuver`…) ; aucune règle
   dans les écrans.

---

## 3. Modèle de données

Notation : `→` clé étrangère ; *(daté)* = `date_debut`, `date_fin` (vide =
en cours) ; tous les modèles héritent des champs d'audit (`created_at`,
`updated_at`, `user_created`, `user_updated`).

### 3.1 Organisation

**Collaborateur** (`User`, existant, enrichi)
- `matricule` (= `username`, unique), `nom`, `prenom`, `email`, `contact`
- `statut` → Statut (actif, suspendu, sorti…)
- `photo`, `last_login`, `last_logout`, `is_active`
- Affectations datées (existantes) : agence, département, poste, catégorie
- **Nouveau** — `SituationVehicule` *(daté)* : `user`, `possede_vehicule`
  (oui/non), `commentaire`

**Département** (`Service`, existant, enrichi)
- `libelle`, `code`, **`parent` → Département** (arbre)

**Agence** (existant) — `nom`, `code`

**Fonction**, **Poste** (existants) — emploi RH, sans rôle dans les circuits

**Responsabilité** (nouveau, référentiel)
- `code` (DG, DAF, CHEF_COMPTABLE, RESP_DEPARTEMENT, RESP_RH…), `libelle`
- `portee` : `globale` | `departement` | `agence`
- `multiple` : plusieurs titulaires simultanés autorisés (oui/non)

**AffectationResponsabilite** (nouveau) *(daté)*
- `user`, `responsabilite`, `departement` (si portée département),
  `agence` (si portée agence), `motif`
- Contrôle : si `multiple = non`, pas deux titulaires sur la même période
  et le même périmètre.
- Le **responsable d'un département** = titulaire de RESP_DEPARTEMENT sur
  ce département à la date considérée.

**AffectationHierarchique** (nouveau) *(daté)* — historique des N+1
- `user` (collaborateur), `mode` : `automatique` | `designe`
- `responsable` → User (obligatoire si mode `designe`)
- `exceptionnelle` (bool), `motif` (obligatoire si exceptionnelle)
- Résolution du N+1 d'un collaborateur à la date D :
  1. ligne en cours à D ; mode `designe` → `responsable` ;
  2. mode `automatique` (ou aucune ligne) → responsable du département du
     collaborateur à D ;
  3. si le collaborateur est lui-même ce responsable (ou département sans
     responsable) → responsable du département parent, en remontant ;
  4. si rien n'est trouvé → N+1 introuvable : soumission bloquée avec un
     message clair et alerte aux administrateurs.

**ImportCollaborateurs** (nouveau) — trace des imports Excel : fichier,
auteur, date, nombre de lignes créées / mises à jour / rejetées, rapport.

### 3.2 Habilitations

**Rôles applicatifs** (groupes Django) :
`super_admin`, `admin`, `admin_workflow`, `admin_finances`, `comptable`,
`direction`, `controleur`, `gestionnaire`, `employe`.

**PerimetreConsultation** (nouveau) : `user`, `type` (tout, département,
agence), `departement`, `agence` — limite ce qu'un profil de consultation
(direction, contrôleur, gestionnaire) voit dans les listes et le reporting.

Les **responsabilités ne donnent pas de droits d'administration** : elles
servent seulement à désigner des valideurs. Un valideur voit les demandes
pour lesquelles il a (ou a eu) une tâche.

### 3.3 Workflow

**ModeleWorkflow** — `type_demande` (1–1), `libelle`, `description`

**VersionWorkflow**
- `modele`, `numero` (1, 2, 3…), `etat` : `brouillon` | `publiee` | `archivee`
- `publiee_le`, `publiee_par`, `commentaire_version`
- `reprise_apres_correction` : `debut` (défaut) | `etape_retour_autorisee`
- Une seule version `publiee` par modèle ; publier archive la précédente.
  Une version publiée ou archivée n'est **jamais modifiable** ; modifier =
  dupliquer en brouillon puis publier.

**Etape**
- `version`, `ordre`, `code`, `libelle`, `active`
- `condition` (JSON, voir §5.3 ; vide = toujours exécutée)
- `mode` : `sequentiel` (défaut) | `parallele`
- `regle_parallele` : `tous` | `un_seul` | `quorum` ; `quorum` (entier)
- `actions_autorisees` : approuver, rejeter, retourner (cases à cocher)
- `champs_modifiables` : liste de champs que le valideur peut corriger
- `delai_heures`, `rappel_apres_heures`, `escalade_apres_heures`,
  `escalade_vers` : `n_plus_1_valideur` | `administrateur` | `personne`
- `auto_validation_demandeur` : `manuelle` | `automatique` | `sauter` | `remonter`
- `meme_valideur_deja_passe` : `approbation_automatique` | `validation_requise`
- `valideur_introuvable` : `bloquer` | `sauter` | `secours` ; `valideur_secours` → User

**RegleDesignation** (une ou plusieurs par étape, l'union des personnes
résolues forme les valideurs de l'étape)
- `etape`, `ordre` (utilisé en mode séquentiel)
- `mode` : `responsabilite` | `personne` | `relation`
- `responsabilite` → Responsabilité ; `perimetre` : `aucun` |
  `departement_demandeur` | `agence_demandeur`
- `personne` → User
- `relation` : `n_plus_1` | `n_plus_2` | `responsable_departement` |
  `responsable_departement_parent`

**InstanceWorkflow** (une par cycle de soumission d'une demande)
- `demande`, `version_workflow`, `cycle` (1, 2… à chaque resoumission),
  `etat` : `en_cours` | `approuvee` | `rejetee` | `retournee` | `annulee`
- `n_plus_1_fige` → User, `date_reference` (date de soumission)
- `plan` (JSON figé : étapes retenues, valideurs prévus, raisons des étapes
  sautées)

**EtapeInstance** — `instance`, `etape`, `ordre`, `etat` : `a_venir` |
`en_cours` | `approuvee` | `rejetee` | `retournee` | `sautee` | `annulee`,
`ouverte_le`, `cloturee_le`, `motif_saut`

**Tache** — `etape_instance`, `valideur_prevu` → User, `ordre` (séquentiel),
`etat` : `en_attente` | `faite` | `annulee` | `expiree`, `echeance`,
`rappels_envoyes`, `escaladee`

**Action** (journal du workflow, en ajout seul)
- `demande`, `instance`, `etape_instance`, `tache`
- `type` : `soumission` | `approbation` | `rejet` | `retour` | `commentaire`
  | `resoumission` | `annulation` | `auto_approbation` | `saut` |
  `escalade` | `reaffectation`
- `auteur_reel` → User, `pour_compte_de` → User (délégation), `delegation`
- `motif` / `commentaire`, `horodatage`, `adresse_ip`, `canal` (web, mobile)
- `auto_validation` (bool : le valideur est le demandeur)

**Delegation**
- `delegant`, `delegataire`, `date_debut`, `date_fin`, `motif`
- `perimetre_types` (vide = tous les types), `perimetre_responsabilites`
  (vide = toutes)
- `etat` : `planifiee` | `active` | `terminee` | `revoquee`

### 3.4 Demandes (socle générique)

**TypeDemande**
- `code` (MLO, MHP, FRC, PAI, RMB, FCM), `libelle`, `famille` : `mission`
  | `simple`, `actif`
- `prefixe_reference`, `devise_defaut`
- `avec_montant` (bool), `paiement_fractionne_autorise` (bool)
- `separation_approbation_paiement` (bool)
- `mode_cloture` : `automatique` | `demandeur`
- `rapport_obligatoire` (bool), `delai_cloture_jours`
- `annulation_demandeur` : statuts dans lesquels le demandeur peut annuler
- `parent_requis` : type de la demande à laquelle elle doit être rattachée
  (FCM → mission)

**ChampType** (formulaire paramétrable des types « simples », et champs
additionnels des types « mission »)
- `type_demande`, `code`, `libelle`, `nature` : texte, texte long, entier,
  montant, date, date-heure, liste, booléen, collaborateur, ville, pays
- `obligatoire`, `options` (pour les listes), `ordre`, `aide`
- `sensible` (bool : sa modification impose la reprise du circuit au début)
- `utilisable_en_condition` (bool)

**Demande**
- `reference` (unique, `PREFIXE-AAAA-NNNNN`), `type_demande`
- `demandeur`, `cree_par` (saisie pour le compte d'un autre, si autorisé)
- `statut` (§4.1), `statut_financier` (§4.2)
- `version_courante` → VersionContenu
- Données organisationnelles **figées à la soumission** : `departement`,
  `agence`, `categorie`, `poste`, `n_plus_1`
- `objet`, `montant_demande`, `devise`, `devise_reference` (figée),
  `montant_demande_ref` (converti dans la devise de référence)
- `montant_approuve`, `montant_paye`, `montant_reverse`, `solde`
- `demande_parent` → Demande (complément, copie d'une demande rejetée)
- `origine_copie` → Demande
- `soumise_le`, `approuvee_le`, `cloturee_le`, `annulee_le`

**VersionContenu** (une par saisie soumise ; l'historique des corrections)
- `demande`, `numero`, `donnees` (JSON des champs du formulaire),
  `calcul` (JSON du récapitulatif financier figé), `soumise_le`,
  `motif_modification`

**Commentaire** — `demande`, `auteur`, `texte`, `visibilite` (tous /
valideurs et gestion), `horodatage`

**CompteurReference** — `type_demande`, `annee`, `dernier_numero`
(incrément sous verrou : numérotation sans trou).

### 3.5 Missions

**Pays** — `code_iso`, `libelle`, `devise_usuelle`
**Ville** — `libelle`, `pays`, `active`
**Distance** — `ville_depart`, `ville_arrivee`, `km` (référentiel validé,
symétrique)

**DetailMission** (1–1 avec Demande pour les familles « mission »)
- `type_mission` : `locale` | `hors_pays`
- `objet`, `motif`, `ville_depart`, `ville_destination`, `pays_destination`
- `depart_le`, `retour_le` (date-heure), `nombre_jours` (calculé)
- `moyen_transport` : `vehicule_personnel` | `vehicule_service` |
  `transport_commun` | `avion` | `autre`
- `possede_vehicule` (figé depuis la situation du salarié)
- `trajet` : `aller_simple` | `aller_retour`
- `distance_referentiel_km`, `distance_retenue_km`,
  `justification_distance`, `distance_validee_par`
- `frais_visa`, `frais_aerien`, `frais_hebergement`, `autres_frais`
  (montant + devise pour chacun)

**LigneCalcul** (récapitulatif figé, une ligne par rubrique)
- `demande`, `version_contenu`, `rubrique` : per_diem, transport, visa,
  aerien, hebergement, autres
- `base` (jours, km…), `tarif`, `devise`, `taux_change`, `montant`,
  `montant_ref` (devise de référence), `bareme_source` (type + id + version),
  `libelle_calcul` (ex. « 4 jours × 25 000 XOF (Cadre, mission locale,
  barème v3) »)

### 3.6 Barèmes (tous datés et versionnés)

Chaque barème a : `date_effet`, `date_fin` (calculée), `motif`,
`modifie_par`, `modifie_le`. Modifier = créer une nouvelle ligne avec une
date d'effet ; l'historique affiche ancien montant, nouveau montant, date
d'effet, date de modification, auteur et motif.

| Barème | Clé | Valeur |
|---|---|---|
| **PerDiem** | type de mission × catégorie | montant, devise |
| **TarifKilometrique** | type de mission (× catégorie, optionnel) | montant par km, devise |
| **TarifTransportVille** | ville de destination (missions locales) | montant aller-retour, devise |
| **ForfaitTransportHorsPays** | — | montant (20 000 par défaut), devise |
| **TauxChange** | devise | taux vers la devise de référence |

Règle de sélection : la ligne dont `date_effet ≤ date de référence` la
plus récente. La date de référence est la **date de soumission** (cycle 1).
Une resoumission après correction **conserve les barèmes du cycle 1**, sauf
si un champ déterminant du calcul change (type de mission, catégorie
figée, ville, dates) : le calcul est alors refait aux barèmes du jour et
l'écart est visible des valideurs.

### 3.7 Trésorerie

**Reglement**
- `demande`, `montant`, `devise`, `taux_change`, `montant_ref`
- `date_paiement`, `mode` : virement, chèque, espèces, mobile money, autre
- `reference`, `beneficiaire` (par défaut le demandeur ou le bénéficiaire
  saisi), `justificatif` → Document
- `enregistre_par`, `annule` (bool), `motif_annulation`

**Reversement**
- `demande`, `montant_du`, `motif` (écart réel / payé, annulation après
  paiement), `etat` : `a_percevoir` | `percu` | `abandonne`
- `percu_le`, `reference`, `justificatif`, `enregistre_par`
- `abandonne` exige un motif et le rôle `admin_finances`.

### 3.8 Documents

**TypePiece** — `code`, `libelle` (ordre de mission, invitation, facture,
reçu, billet, rapport de mission, justificatif de dépense, justificatif de
paiement, document comptable), `duree_conservation_ans`

**ExigencePiece** — `type_demande`, `type_piece`, `moment` : `soumission`
| `etape` (→ Etape) | `paiement` | `cloture`, `obligatoire`

**Document**
- `demande`, `type_piece`, `fichier`, `nom_origine`, `taille`, `empreinte`
  (SHA-256), `version_contenu`, `ajoute_par`, `ajoute_le`
- `remplace` → Document (remplacement), `retire` (bool) + `motif`
- Jamais de suppression physique après soumission ; retrait logique tracé.
- Formats autorisés : PDF, JPEG, PNG, WebP, Office ; taille max paramétrable
  (10 Mo par défaut).

### 3.9 Notifications

**Notification** — `destinataire`, `evenement`, `demande`, `titre`,
`message`, `lue`, `creee_le`
**ModeleMessage** — `evenement`, `canal`, `objet`, `corps` (variables :
référence, demandeur, étape, motif, lien)
**PreferenceNotification** — `user`, `evenement`, `canal`, `actif`
(certains événements ne sont pas désactivables, ex. validation attendue)
**AppareilMobile** — `user`, `jeton_fcm`, `plateforme`

### 3.10 Audit

**JournalActivite** (ajout seul, jamais modifié)
- `horodatage`, `auteur`, `pour_compte_de`, `action`, `objet_type`,
  `objet_id`, `avant` (JSON), `apres` (JSON), `motif`, `adresse_ip`,
  `agent` (navigateur / app), `canal`

### 3.11 Paramètres système

**ParametreSysteme** (une seule ligne, rôle `admin_finances` / `admin`)
- `devise_reference` (code ISO, ex. XOF) : devise des totaux, des
  conversions et du reporting.
- Changement : possible tant qu'aucune demande n'a été soumise. Ensuite,
  il ne s'applique qu'aux nouvelles demandes, chaque demande gardant sa
  propre `devise_reference` figée ; le reporting signale alors les
  montants exprimés dans une autre devise de référence (aucune
  reconversion silencieuse).
- Autres réglages globaux : calendrier (jours ouvrés, jours fériés),
  taille maximale des pièces, durée de session, activation des canaux
  (push, e-mail).

---

## 4. Cycles de vie

### 4.1 Statut de la demande

```
                ┌──────────── annuler ─────────────┐
                ▼                                  │
 BROUILLON ──soumettre──► EN_VALIDATION ──dernière approbation──► APPROUVEE
    ▲                      │   │   │                                │
    │                      │   │   └──rejeter──► REJETEE (final)    │
    │       retourner ◄────┘   │                                    │
    │          │               └──annuler──► ANNULEE (final)        │
    │          ▼                                                    │
    └─── A_CORRIGER ──resoumettre──► EN_VALIDATION                  │
              │                                                     │
              └──annuler──► ANNULEE                                 │
                                                                    ▼
        mode clôture automatique : APPROUVEE ──(payée ou sans montant)──► CLOTUREE
        mode clôture demandeur  : APPROUVEE ──► EN_ATTENTE_CLOTURE ──conditions remplies──► CLOTUREE
```

| Transition | Qui | Conditions |
|---|---|---|
| Brouillon → En validation | Demandeur | Champs et pièces obligatoires complets, N+1 résolu, plan de validation calculable |
| En validation → À corriger | Valideur de l'étape en cours | Action « retourner » autorisée à l'étape, motif obligatoire |
| En validation → Rejetée | Valideur de l'étape en cours | Action « rejeter » autorisée, motif obligatoire |
| En validation → Approuvée | Moteur | Dernière étape approuvée |
| À corriger → En validation | Demandeur | Nouvelle version de contenu |
| Brouillon → (supprimée) | Demandeur | Seul cas de suppression physique |
| En validation / À corriger → Annulée | Demandeur | Si autorisé par le type (`annulation_demandeur`), motif obligatoire |
| Approuvée → Annulée | Procédure d'annulation (§4.3) | — |
| Approuvée → En attente de clôture | Moteur | Mode clôture « demandeur » |
| → Clôturée | Moteur ou contrôleur | Conditions de clôture (§9) |

Une demande **Rejetée, Annulée ou Clôturée** est figée définitivement ;
seule l'action « Dupliquer en nouvelle demande » est disponible.

### 4.2 Statut financier

`SANS_OBJET` (pas de montant) · `A_PAYER` (approuvée) ·
`PARTIELLEMENT_PAYEE` · `PAYEE` · `REVERSEMENT_ATTENDU` · `SOLDEE`

- `A_PAYER` dès l'approbation si `montant_approuve > 0`.
- `PARTIELLEMENT_PAYEE` si `0 < montant_paye < montant_approuve`
  (uniquement si le type autorise le fractionnement).
- `PAYEE` si `montant_paye = montant_approuve`.
- `REVERSEMENT_ATTENDU` si un reversement est à percevoir (clôture ou
  annulation après paiement).
- `SOLDEE` quand plus rien n'est dû dans un sens ni dans l'autre.

### 4.3 Annulation selon le statut

| Statut | Procédure |
|---|---|
| Brouillon | Suppression libre par le demandeur |
| En validation, À corriger | Annulation directe par le demandeur (si autorisée par le type), motif obligatoire ; les tâches ouvertes sont annulées et les valideurs notifiés |
| Approuvée, non payée | **Demande d'annulation** : type de demande dédié, rattaché, avec son propre workflow (par défaut : N+1 puis DAF). Approuvée → la demande initiale passe Annulée |
| Approuvée, payée (même partiellement) | Même procédure, et création d'un **reversement** du montant payé |

---

## 5. Moteur de workflow

### 5.1 Paramétrage par l'administrateur

Écran « Workflows » (rôle `admin_workflow`) :
- liste des types de demande et de leur version publiée ;
- édition d'une **version brouillon** : ajout, suppression, réordonnancement
  (glisser-déposer), activation des étapes, conditions, valideurs, règles ;
- **simulation** : on choisit un demandeur et des valeurs (montant, type
  de mission…), le moteur affiche le plan de validation qui en résulterait
  et les raisons des étapes sautées ;
- **publication** avec commentaire de version ; comparaison entre versions.

Contrôles à la publication : au moins une étape active, ordres cohérents,
quorum ≤ nombre de valideurs possibles, chaque règle de désignation
complète, conditions valides.

### 5.2 Désignation des valideurs

| Mode | Paramètre | Résolution à la date de référence |
|---|---|---|
| Par responsabilité | Responsabilité + périmètre | Titulaires en cours de la responsabilité (sur le département / l'agence du demandeur si périmètre) |
| Par personne | Collaborateur | Ce collaborateur (s'il est actif) |
| Par relation | n_plus_1, n_plus_2, responsable_departement, responsable_departement_parent | N+1 figé de la demande ; N+2 = N+1 du N+1 ; responsable du département figé |

Plusieurs titulaires pour une responsabilité : ils deviennent tous
valideurs de l'étape, et la règle de l'étape s'applique (en séquentiel, ils
sont classés par ordre alphabétique ; il est conseillé d'utiliser le mode
parallèle « un seul » dans ce cas, ce que l'écran suggère).

Personne inactive ou introuvable : comportement `valideur_introuvable` de
l'étape (bloquer avec alerte administrateur, sauter avec trace, ou valideur
de secours).

### 5.3 Conditions d'exécution

Structure JSON évaluée par le moteur (pas de code libre) :

```json
{ "et": [
    { "champ": "montant_demande_ref", "op": ">", "valeur": 1000000 },
    { "ou": [
        { "champ": "categorie", "op": "=", "valeur": "CADRE" },
        { "champ": "type_mission", "op": "=", "valeur": "hors_pays" } ] } ] }
```

- Opérateurs : `=`, `≠`, `>`, `≥`, `<`, `≤`, `dans`, `pas dans`, `vide`,
  `non vide`.
- Champs disponibles : `type_demande`, `montant_demande_ref`, `categorie`,
  `departement` (avec option « ou un de ses sous-départements »), `agence`,
  `type_mission`, `pays_destination`, `nombre_jours`, et tout `ChampType`
  marqué `utilisable_en_condition`.
- L'écran propose un éditeur visuel (lignes « champ / opérateur / valeur »,
  groupes ET / OU) ; le JSON n'est jamais saisi à la main.

### 5.4 Exécution

**À la soumission**
1. Contrôle des champs et pièces obligatoires.
2. Figer : version du workflow publiée, N+1, département, agence,
   catégorie, poste, barèmes, calcul.
3. Calcul du **plan de validation** : pour chaque étape active, évaluer la
   condition ; résoudre les valideurs ; appliquer les règles
   d'auto-validation et de « même valideur déjà passé ». Le plan est
   enregistré avec les raisons (« étape DG sautée : montant ≤ 1 000 000 »).
4. Le plan est montré au demandeur **avant** confirmation de la soumission.
5. Ouverture de la première étape.

**Ouverture d'une étape**
- Vérification des valideurs prévus : un titulaire de responsabilité qui a
  quitté sa fonction est remplacé par le titulaire en cours (trace
  « valideur re-résolu »). Le N+1 n'est jamais re-résolu (figé).
- Application des délégations actives (§5.7).
- Création des tâches : toutes en mode parallèle ; la première seulement en
  mode séquentiel.
- Notifications « validation attendue ».

**Action d'un valideur** (le service vérifie qu'il détient une tâche en
attente, directement ou par délégation)
- **Approuver** : tâche faite. Séquentiel → tâche suivante, ou étape
  approuvée si c'était la dernière. Parallèle → étape approuvée quand la
  règle est atteinte (tous / un seul / quorum) ; les tâches restantes sont
  alors annulées.
- **Rejeter** (motif obligatoire) : étape rejetée, instance rejetée,
  demande Rejetée, toutes les tâches annulées.
- **Retourner** (motif obligatoire) : étape retournée, instance retournée,
  demande À corriger. En parallèle, un seul retour suffit.
- **Commenter** : sans effet sur le circuit, visible dans l'historique.
- En parallèle « tous » ou « quorum », un rejet est immédiat : il n'attend
  pas les autres valideurs.

**Auto-validation du demandeur** (paramètre de l'étape)
- `manuelle` : la tâche est créée pour le demandeur, qui doit approuver
  lui-même ; l'action est marquée `auto_validation`.
- `automatique` : le moteur approuve l'étape, action `auto_approbation`
  tracée.
- `sauter` : l'étape est sautée, trace dans le plan.
- `remonter` : l'étape est confiée au N+1 du demandeur.

**Même valideur déjà passé** (paramètre de l'étape) : s'il a déjà approuvé
une étape précédente de ce cycle, soit approbation automatique tracée,
soit nouvelle validation exigée.

### 5.5 Retour pour correction et resoumission

- Le demandeur voit le motif, modifie les champs autorisés, ajoute ou
  remplace des pièces et resoumet. Une **nouvelle version de contenu** est
  créée ; l'ancienne reste consultable, avec un comparatif champ par champ.
- Nouveau **cycle** d'instance, sur la **même version de workflow** que le
  cycle 1 (le circuit ne change pas en cours de vie d'une demande).
- Reprise :
  - par défaut, depuis la **première étape** ;
  - si la version l'autorise (`etape_retour_autorisee`) **et** qu'aucun
    champ `sensible` n'a changé **et** que le calcul financier est
    identique, reprise **à l'étape qui a retourné** : les approbations
    antérieures du cycle précédent sont reprises et affichées comme telles.

### 5.6 Rejet

Final. Bouton « Dupliquer en nouvelle demande » : crée un brouillon avec le
même contenu (hors pièces, à joindre de nouveau ou à recopier au choix),
lié par `origine_copie`.

### 5.7 Délégations

- Créées par le délégant ou par un administrateur (motif obligatoire dans
  ce cas).
- Pendant la période active, les **nouvelles tâches** du délégant entrant
  dans le périmètre sont **aussi** visibles par le délégataire (le délégant
  garde la main). Option : transférer les tâches déjà en attente.
- Interdits : déléguer à soi-même ; délégataire = demandeur de la demande
  concernée (la tâche reste alors au délégant) ; délégation en chaîne
  (un délégataire ne peut pas re-déléguer ce qu'il a reçu).
- Traçabilité : `auteur_reel` = délégataire, `pour_compte_de` = délégant.
- Changement d'état automatique (planifiée → active → terminée) par la
  tâche planifiée ; révocation possible à tout moment.

### 5.8 Délais, rappels, escalades

- `echeance` = ouverture + `delai_heures` (jours ouvrés paramétrables :
  week-ends et jours fériés exclus, calendrier des jours fériés géré dans
  l'application).
- Rappel au valideur après `rappel_apres_heures`, puis chaque jour.
- Escalade après `escalade_apres_heures` : notification au destinataire
  d'escalade (la tâche reste au valideur ; l'administrateur peut
  réaffecter).
- Les demandes en retard alimentent les tableaux de bord.

### 5.9 Réaffectation exceptionnelle

Rôle `admin_workflow` : remplacer le valideur d'une tâche en attente ou le
N+1 figé d'une demande en cours, avec **motif obligatoire**. Action
`reaffectation` dans le journal (ancien, nouveau, motif, auteur).

### 5.10 Versionnement

- Une demande garde la version de workflow de sa première soumission
  jusqu'à sa clôture, y compris après correction.
- Publier une nouvelle version n'affecte que les demandes soumises après.
- Les versions archivées restent consultables (et leur simulation).

---

## 6. Types de demandes

| Code | Type | Famille | Montant | Particularités |
|---|---|---|---|---|
| MLO | Mission locale | mission | oui | Per diem, transport (km ou tarif ville) |
| MHP | Mission hors pays | mission | oui | Per diem en devise, visa, aérien, hébergement, devises |
| FRC | Frais de réception client | simple | oui | Champs : date, client, objet, participants, lieu, montant, justification |
| PAI | Demande de paiement | simple | oui | Bénéficiaire (tiers), motif, montant, devise, mode de paiement, référence initiale |
| RMB | Demande de remboursement | simple | oui | Frais avancés par le salarié, justificatifs obligatoires |
| FCM | Frais complémentaires de mission | simple | oui | Rattachée à une mission approuvée (MLO / MHP) ; motif ; montants ; justificatifs |
| ANN | Demande d'annulation | simple | non | Rattachée à une demande approuvée (§4.3) |

- **Types simples** : formulaire défini par les `ChampType`. Un nouveau type
  simple se crée **sans développement** : type + champs + pièces exigées +
  workflow.
- **Types mission** : formulaire et calcul codés (§7), complétés au besoin
  par des `ChampType` additionnels.
- **Frais complémentaires** : le montant approuvé de la mission initiale ne
  change jamais. La fiche mission affiche « engagé total = mission +
  compléments approuvés », « payé total », « solde ».

---

## 7. Règles de calcul des missions

### 7.1 Nombre de jours
`nombre_jours = date(retour) − date(départ) + 1` (jours calendaires).
Départ et retour le même jour = 1 jour. Pas de demi-journée. Retour avant
départ : refusé.

### 7.2 Per diem
`per diem = nombre_jours × tarif(type_mission, catégorie)` dans la devise du
barème. La catégorie est celle du demandeur **à la date de départ** (figée).

### 7.3 Transport (mission locale)
- **Avec véhicule** (`possede_vehicule` et moyen = véhicule personnel) :
  `distance retenue × tarif km`. Distance retenue = distance du référentiel
  × 2 si aller-retour. Saisie d'une autre distance : justification
  obligatoire et validation par l'étape désignée (champ `distance_retenue_km`
  dans les `champs_modifiables` de cette étape).
- **Sans véhicule** : `tarif ville de destination` (aller-retour inclus,
  identique pour toutes les catégories). Ville sans tarif : saisie manuelle
  justifiée, signalée aux valideurs.
- **Véhicule de service** : pas d'indemnité de transport.

### 7.4 Mission hors pays
- Per diem : barème hors pays (montant et devise paramétrables).
- **Transport** : forfait fixe pour se rendre à l'aéroport (barème
  `ForfaitTransportHorsPays`, 20 000 par défaut), quel que soit le moyen
  de transport. Le demandeur peut l'ajuster sur sa demande avec une
  justification obligatoire ; l'écart avec le barème est signalé aux
  valideurs.
- Visa, billet d'avion, hébergement, autres frais : chaque montant avec sa
  devise.

### 7.5 Devises
- Chaque ligne est convertie dans la **devise de référence** (paramètre
  système, §3.11) au **taux figé à la soumission** (barème `TauxChange`).
- Le récapitulatif affiche le montant en devise d'origine et en devise de
  référence ; le total prévisionnel est en devise de référence.
- Les règlements sont enregistrés dans leur devise réelle avec leur taux.

### 7.6 Récapitulatif affiché

Exemple avec XOF comme devise de référence :

| Rubrique | Base | Tarif | Montant |
|---|---|---|---|
| Indemnités journalières | 4 jours | 25 000 XOF (Cadre, locale, barème du 01/01/2026) | 100 000 XOF |
| Transport | Abidjan → Bouaké, tarif ville | 30 000 XOF (A/R) | 30 000 XOF |
| Hébergement | — | — | 60 000 XOF |
| **Total prévisionnel** | | | **190 000 XOF** |

Le calcul est figé dans `LigneCalcul` ; les valideurs voient exactement ce
que le demandeur a vu.

---

## 8. Trésorerie

### 8.1 File à payer
Rôle `comptable` : demandes `A_PAYER` ou `PARTIELLEMENT_PAYEE`, filtres
(type, département, agence, date d'approbation, montant), export.

### 8.2 Enregistrement d'un règlement
- Montant ≤ solde restant. Si le type n'autorise pas le fractionnement :
  un seul règlement, égal au montant approuvé.
- Séparation des tâches (si activée sur le type) : refus si le comptable a
  approuvé une étape de la demande.
- Justificatif de paiement exigé si l'exigence est paramétrée.
- Annulation d'un règlement (erreur de saisie) : motif obligatoire, rôle
  `admin_finances`, trace.
- Notifications : « paiement effectué » au demandeur.

### 8.3 Montants suivis
Montant demandé · montant approuvé · montant payé · solde restant ·
montant réel (clôture) · reversement dû / perçu.

### 8.4 Reversement
- À la clôture : `reversement = montant payé − dépenses réelles retenues`
  si positif.
- À l'annulation après paiement : reversement du montant payé.
- La comptabilité enregistre la perception ; la demande ne se clôture
  qu'une fois le reversement perçu (ou abandonné par `admin_finances` avec
  motif).

---

## 9. Clôture

| Mode | Déroulement |
|---|---|
| **A — automatique** | Après la dernière validation : Clôturée dès que la demande est payée (ou immédiatement si sans montant) |
| **B — par le demandeur** | Après la dernière validation : En attente de clôture. Le demandeur joint le rapport (si obligatoire), les justificatifs exigés, déclare les dépenses réelles et les informations de réalisation (dates réelles, observations), puis soumet la clôture |

Conditions de clôture (mode B), toutes requises :
1. éléments de clôture soumis (rapport si obligatoire, pièces exigées au
   moment `cloture`) ;
2. demande payée (statut financier `PAYEE`) ;
3. aucun reversement à percevoir ;
4. optionnel par type : contrôle des éléments de clôture par un rôle
   (`controleur` ou comptable), qui peut les **retourner** au demandeur
   avec motif.

Rappels automatiques au demandeur après le retour de mission
(`delai_cloture_jours`) ; demandes non clôturées visibles dans les
tableaux de bord.

---

## 10. Documents

- Ajout à tout moment autorisé par le statut : brouillon (demandeur),
  correction (demandeur), étape (valideur, si l'étape l'autorise), paiement
  (comptable), clôture (demandeur).
- Accès : demandeur, valideurs passés et présents de la demande, comptables,
  profils de consultation dans leur périmètre, administrateurs.
- Téléchargement par URL signée et temporaire ; jamais de lien public.
- Historique : ajout, remplacement, retrait logique (motif), consultation
  des pièces sensibles.
- Conservation : durée par type de pièce (10 ans par défaut pour les pièces
  comptables) ; purge uniquement par une procédure administrative tracée.
- Génération PDF : **ordre de mission** et **fiche de demande** avec le
  circuit de validation complet (noms, dates, commentaires) et un QR code
  de vérification (page publique indiquant seulement si le document est
  authentique et son statut).

---

## 11. Notifications

| Événement | Destinataires | Canaux par défaut |
|---|---|---|
| Nouvelle demande soumise | Demandeur (accusé) | App |
| Validation attendue | Valideurs de l'étape (et délégataires) | App, push, e-mail |
| Validation effectuée | Demandeur | App |
| Demande rejetée | Demandeur | App, push, e-mail |
| Demande retournée pour correction | Demandeur | App, push, e-mail |
| Demande resoumise | Valideurs de l'étape de reprise | App, push |
| Demande approuvée | Demandeur | App, push, e-mail |
| Paiement en attente | Comptables | App |
| Paiement effectué | Demandeur | App, push |
| Demande en attente de clôture / rapport attendu | Demandeur | App, push, e-mail |
| Reversement à effectuer | Demandeur, comptables | App, e-mail |
| Demande clôturée | Demandeur | App |
| Rappel / retard | Valideur ; puis destinataire d'escalade | App, push, e-mail |
| Délégation reçue | Délégataire | App, e-mail |

- Envoi après validation de la transaction (jamais de notification pour
  une action annulée).
- Canal e-mail désactivé tant que le SMTP n'est pas configuré ; les
  notifications applicatives fonctionnent seules.
- Préférences par utilisateur ; « validation attendue » n'est pas
  désactivable.

---

## 12. Profils et droits

| Profil | Peut |
|---|---|
| **Collaborateur** (employe) | Créer, soumettre, corriger, annuler (selon règles), clôturer ses demandes ; consulter ses demandes ; déléguer ses validations |
| **Valideur** (toute personne ayant une tâche) | Voir les demandes où il a une tâche ; approuver, rejeter, retourner, commenter ; ajouter des pièces si l'étape le permet |
| **Comptable** | File à payer, règlements, reversements, contrôle de clôture (si paramétré) |
| **Direction** | Tableaux de bord et consultation dans son périmètre |
| **Contrôleur** | Consultation et audit dans son périmètre, contrôle de clôture |
| **Gestionnaire** | Consultation des demandes de ses agences / départements |
| **Admin workflow** | Workflows, versions, simulation, délégations pour autrui, réaffectations |
| **Admin finances** | Barèmes, taux de change, villes et distances, annulation de règlement, abandon de reversement |
| **Admin** | Organisation (collaborateurs, départements, responsabilités, N+1), import Excel, types de demande, pièces, notifications |
| **Super admin** | Tout, dont la gestion des administrateurs |

Les profils sont cumulables. Toute vérification de droit est faite par
l'API ; les écrans masquent seulement ce qui n'est pas accessible.

---

## 13. Sécurité et audit

- Authentification JWT (accès 1 h, renouvellement 1 jour, liste de
  révocation), limitation des tentatives, mot de passe fort, mot de passe
  oublié par SMS.
- Double authentification (application TOTP) **optionnelle**, imposable
  aux administrateurs et valideurs financiers.
- Expiration de session sur inactivité (web), déconnexion de tous les
  appareils.
- HTTPS obligatoire en production.
- Contrôle d'accès par objet : chaque requête vérifie le lien entre
  l'utilisateur et la demande (demandeur, tâche, périmètre, rôle).
- Gel des données : après soumission, seuls les champs ouverts par l'étape
  en cours sont modifiables. Correction exceptionnelle par un administrateur
  via une action motivée, journalisée avec l'avant et l'après.
- Journal d'activité en ajout seul, consultable et exportable par les
  administrateurs et contrôleurs.
- Sauvegardes quotidiennes de la base et des fichiers, vérifiées, copie
  hors serveur (déjà en place côté déploiement).

---

## 14. Tableaux de bord et reporting

| Profil | Indicateurs |
|---|---|
| Collaborateur | Mes demandes par statut (brouillon, en cours, approuvées, rejetées, à corriger, à clôturer), historique des missions, reversements dus |
| Valideur | À traiter, en attente, en retard, historique des validations, répartition par département et par type |
| Direction | Nombre de missions, locale / hors pays, dépenses par département, par catégorie, par agence ; montants demandés / approuvés / payés ; engagements (approuvé non payé) ; évolution mensuelle |
| Comptabilité | À payer, payées, partielles, soldes restants, reversements à percevoir, historique des règlements |
| Administrateur | Utilisateurs, rôles, responsabilités, départements, workflows et versions, barèmes et historique, journal d'activité, imports |

Filtres communs : période, type, statut, département, agence, catégorie,
demandeur. Exports Excel et PDF de toute liste et de tout tableau. Les
montants agrégés sont dans la devise de référence (taux figés).

---

## 15. API (principaux points d'entrée)

Préfixe `/api/v1/`. Format JSON, pagination, filtres, tri.

| Domaine | Points d'entrée |
|---|---|
| Organisation | `collaborateurs/`, `collaborateurs/{id}/n-plus-1/?date=`, `departements/` (arbre), `responsabilites/`, `affectations-responsabilite/`, `affectations-hierarchiques/`, `situations-vehicule/`, `imports-collaborateurs/` |
| Workflow (admin) | `workflows/`, `workflows/{id}/versions/`, `versions/{id}/etapes/`, `versions/{id}/publier/`, `versions/{id}/dupliquer/`, `versions/{id}/simuler/` |
| Demandes | `types-demande/`, `demandes/` (CRUD brouillon), `demandes/{id}/plan/` (prévisualisation), `demandes/{id}/soumettre/`, `/resoumettre/`, `/annuler/`, `/dupliquer/`, `/historique/`, `/versions/`, `/commentaires/`, `/documents/`, `/cloture/` |
| Validation | `taches/` (mes tâches, filtres), `taches/{id}/approuver/`, `/rejeter/`, `/retourner/`, `taches/{id}/reaffecter/` (admin) |
| Délégations | `delegations/`, `delegations/{id}/revoquer/` |
| Missions | `missions/calculer/` (calcul à blanc pendant la saisie), `villes/`, `pays/`, `distances/` |
| Barèmes | `baremes/per-diem/`, `baremes/kilometrique/`, `baremes/transport-ville/`, `baremes/forfait-hors-pays/`, `baremes/taux-change/` (avec historique), `parametres-systeme/` |
| Trésorerie | `a-payer/`, `reglements/`, `reglements/{id}/annuler/`, `reversements/`, `reversements/{id}/percevoir/` |
| Notifications | `notifications/`, `notifications/tout-lire/`, `appareils/`, `preferences-notification/` |
| Reporting | `tableaux-de-bord/{profil}/`, `exports/{liste}.xlsx`, `exports/{liste}.pdf` |
| Audit | `journal/` |

Les actions métier sont des points d'entrée dédiés (`/soumettre/`,
`/approuver/`…) : jamais de changement de statut par simple mise à jour
d'un champ.

---

## 16. Application mobile

Périmètre : connexion, tableau de bord personnel, création et suivi des
demandes, calcul en direct des frais de mission, validation (approuver,
rejeter, retourner, commenter), pièces jointes (appareil photo, fichiers),
notifications push avec ouverture directe de la demande, soumission des
éléments de clôture et du rapport, délégations.

Non prévus sur mobile : administration, paramétrage des workflows et des
barèmes, trésorerie, reporting avancé.

---

## 17. Découpage en lots

| Lot | Contenu | Critères de fin |
|---|---|---|
| **1. Organisation** | Matricule, statut, situation véhicule, départements hiérarchisés, responsabilités, N+1 (modes, historique, réaffectation), rôles métier, import Excel | Résolution du N+1 et des titulaires à une date donnée testée ; import Excel avec rapport d'erreurs |
| **2. Moteur et socle** | Types de demande, champs paramétrables, demandes, versions de contenu, numérotation, workflow (versions, étapes, conditions, désignation, simulation), tâches, actions, retours, rejets, annulations, délégations, pièces jointes, journal, notifications in-app | Type FRC entièrement opérationnel sur web ; tous les scénarios du moteur couverts par des tests automatisés |
| **3. Barèmes et missions** | Devise de référence, per diem, tarifs km, tarifs par ville, forfait transport hors pays, taux de change, villes, distances ; MLO et MHP ; calcul et figement | Calculs conformes au §7 ; changement de barème sans effet sur les demandes existantes |
| **4. Paiement et trésorerie** | PAI, RMB, FCM, ANN ; file à payer, règlements fractionnés, séparation des tâches, reversements | Statuts financiers conformes au §4.2 |
| **5. Clôture** | Modes A et B, rapport, pièces de clôture, dépenses réelles, reversement, contrôle de clôture | Une mission va de la création à la clôture avec reversement |
| **6. Pilotage et canaux** | Tableaux de bord par profil, exports Excel/PDF, PDF ordre de mission avec QR code, push Firebase, e-mail SMTP, rappels, escalades, jours fériés | Indicateurs vérifiés sur un jeu de données de test |
| **7. Mobile** | Périmètre du §16 | Parcours demandeur et valideur complets sur Android et iOS |

Chaque lot livre l'API, les écrans web correspondants et les tests ; le
mobile suit dès le lot 2 pour la consultation et la validation.

---

## 18. Points laissés ouverts

| Sujet | Statut |
|---|---|
| Mission collective | Hors périmètre (D6) ; le modèle `DetailMission` pourra recevoir des lignes participants |
| Serveur SMTP | À définir (D13) |
| Système RH cible | À définir (D15) ; import Excel en attendant |
| Calendrier des jours fériés | À saisir par l'administrateur |
| Transport des missions hors pays | Forfait aéroport (D16) |
