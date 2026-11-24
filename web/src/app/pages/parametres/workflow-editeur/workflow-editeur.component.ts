// src/app/pages/parametres/workflow-editeur/workflow-editeur.component.ts
//
// Éditeur d'une version de circuit : étapes (ordre, mode, règles de
// désignation, condition, comportements), contrôle, publication et
// simulation. Une version publiée ou archivée est en lecture seule.

import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { forkJoin } from 'rxjs';
import {
  ChampCondition, DemandesService, EntreePlan, Etape, RegleDesignation, TypeDemande, VersionWorkflow,
} from 'src/app/core/services/demandes/demandes.service';
import { OrganisationService, Responsabilite, messageErreur } from 'src/app/core/services/organisation/organisation.service';

interface LigneCondition { champ: string; op: string; valeur: any; }

@Component({
  selector: 'app-workflow-editeur',
  templateUrl: './workflow-editeur.component.html',
})
export class WorkflowEditeurComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  version: VersionWorkflow | null = null;
  type: TypeDemande | null = null;
  responsabilites: Responsabilite[] = [];
  collaborateurs: { id: number; libelle: string }[] = [];
  champsCondition: ChampCondition[] = [];
  operateurs: { code: string; libelle: string }[] = [];
  categories: any[] = [];
  departements: any[] = [];
  agences: any[] = [];
  erreursControle: string[] | null = null;
  commentairePublication = '';

  // Étape en cours d'édition (copie locale)
  edition: Etape | null = null;
  conditionGroupe: 'et' | 'ou' = 'et';
  conditionLignes: LigneCondition[] = [];
  conditionAvancee = false;

  // Simulation
  simDemandeur: number | null = null;
  simMontant: any = null;
  simDonnees: Record<string, any> = {};
  simResultat: { demandeur: any; n_plus_1: any; departement: string | null; plan: EntreePlan[] } | null = null;

  readonly relations = [['n_plus_1', 'N+1 du demandeur'], ['n_plus_2', 'N+2 du demandeur'],
    ['responsable_departement', 'Responsable du département du demandeur'], ['responsable_departement_parent', 'Responsable du département parent']];
  readonly perimetres = [['aucun', 'Aucun'], ['departement_demandeur', 'Département du demandeur'], ['agence_demandeur', 'Agence du demandeur']];
  readonly autoValidations = [['manuelle', 'Il valide lui-même (manuellement)'], ['automatique', 'Approbation automatique'],
    ['sauter', "L'étape est sautée"], ['remonter', 'Confiée à son N+1']];
  readonly memeValideur = [['validation_requise', 'Nouvelle validation exigée'], ['approbation_automatique', 'Approbation automatique']];
  readonly introuvable = [['bloquer', 'Bloquer la soumission'], ['sauter', "Sauter l'étape"], ['secours', 'Valideur de secours']];
  readonly escalades = [['n_plus_1_valideur', 'N+1 du valideur'], ['administrateur', 'Administrateurs des workflows'],
                        ['personne', 'Une personne désignée']];

  ngOnInit(): void {
    this.organisation.responsabilites().subscribe(r => this.responsabilites = r);
    this.organisation.collaborateursTous().subscribe(u => this.collaborateurs = (u ?? []).filter(x => x.is_active)
      .map(x => ({ id: x.id, libelle: `${x.nom} ${x.prenom} (${x.username})` })));
    this.organisation.departementsTous().subscribe(d => this.departements = d);
    this.organisation.agencesToutes().subscribe(a => this.agences = a);
    this.organisation.categoriesToutes().subscribe(c => this.categories = c);
    this.route.paramMap.subscribe(p => this.charger(Number(p.get('id'))));
  }

  private champsCorrigeablesCache: { code: string; libelle: string }[] = [];
  /** Montant approuvé + champs du type (liste stable pour ng-select) */
  get champsCorrigeables(): { code: string; libelle: string }[] {
    const attendu = 1 + (this.type?.champs?.length ?? 0);
    if (this.champsCorrigeablesCache.length !== attendu) {
      this.champsCorrigeablesCache = [{ code: 'montant_approuve', libelle: 'Montant approuvé' },
        ...(this.type?.champs ?? []).map(c => ({ code: c.code, libelle: c.libelle }))];
    }
    return this.champsCorrigeablesCache;
  }

  get modifiable(): boolean { return this.version?.etat === 'brouillon'; }

  charger(id = this.version?.id): void {
    if (!id) return;
    this.service.versionWorkflow(id).subscribe({
      next: v => {
        this.version = v;
        if (!this.type || this.type.id !== v.type_demande) {
          forkJoin({ types: this.service.types(true), champs: this.service.champsCondition(v.type_demande) }).subscribe(r => {
            this.type = r.types.find(t => t.id === v.type_demande) ?? null;
            this.champsCondition = r.champs.champs;
            this.operateurs = r.champs.operateurs;
          });
        }
      },
      error: e => { this.toast.error(messageErreur(e)); this.router.navigate(['/parametres/workflows']); },
    });
  }

  libelle(liste: string[][], code: string): string { return liste.find(x => x[0] === code)?.[1] ?? code; }

  descriptionRegle(r: RegleDesignation): string {
    if (r.mode === 'personne') return `Personne : ${r.personne_nom ?? this.collaborateurs.find(c => c.id === r.personne)?.libelle ?? '—'}`;
    if (r.mode === 'relation') return this.libelle(this.relations, r.relation);
    const resp = r.responsabilite_libelle ?? this.responsabilites.find(x => x.id === r.responsabilite)?.libelle ?? '—';
    return r.perimetre !== 'aucun' ? `${resp} (${this.libelle(this.perimetres, r.perimetre).toLowerCase()})` : resp;
  }

  // ── Étapes ───────────────────────────────────────────────
  nouvelleEtape(): void {
    if (!this.version) return;
    this.ouvrirEdition({
      version: this.version.id, code: `etape_${this.version.etapes.length + 1}`, libelle: '', active: true, condition: null,
      mode: 'sequentiel', regle_parallele: 'tous', quorum: null, actions_autorisees: ['approuver', 'rejeter', 'retourner'],
      champs_modifiables: [], auto_validation_demandeur: 'manuelle', meme_valideur_deja_passe: 'validation_requise',
      valideur_introuvable: 'bloquer', valideur_secours: null, delai_heures: null, rappel_apres_heures: null,
      escalade_apres_heures: null, escalade_vers: 'n_plus_1_valideur', escalade_personne: null, regles: [{ mode: 'relation', relation: 'n_plus_1', responsabilite: null, perimetre: 'aucun', personne: null }],
    });
  }

  ouvrirEdition(e: Etape): void {
    this.edition = JSON.parse(JSON.stringify(e));
    const c = e.condition;
    this.conditionAvancee = false;
    this.conditionGroupe = 'et';
    this.conditionLignes = [];
    if (c) {
      const groupe = c.et ? 'et' : c.ou ? 'ou' : null;
      const enfants: any[] = groupe ? c[groupe] : [c];
      if (enfants.every(x => x.champ)) {
        this.conditionGroupe = (groupe ?? 'et') as 'et' | 'ou';
        this.conditionLignes = enfants.map(x => ({ champ: x.champ, op: x.op, valeur: x.valeur }));
      } else {
        this.conditionAvancee = true;  // groupes imbriqués : non modifiables ici
      }
    }
  }

  basculerAction(a: string): void {
    if (!this.edition || a === 'approuver') return;
    const l = new Set(this.edition.actions_autorisees);
    l.has(a) ? l.delete(a) : l.add(a);
    this.edition.actions_autorisees = [...l];
  }

  ajouterRegle(): void {
    this.edition?.regles.push({ mode: 'responsabilite', responsabilite: null, perimetre: 'aucun', personne: null, relation: '' });
  }

  regleResponsabilite(r: RegleDesignation): void {
    const resp = this.responsabilites.find(x => x.id === r.responsabilite);
    if (resp?.portee === 'departement') r.perimetre = 'departement_demandeur';
    else if (resp?.portee === 'agence') r.perimetre = 'agence_demandeur';
    else r.perimetre = 'aucun';
  }

  natureChamp(code: string): string { return this.champsCondition.find(c => c.code === code)?.nature ?? 'texte'; }
  optionsChamp(code: string): string[] { return this.champsCondition.find(c => c.code === code)?.options ?? []; }

  ajouterLigneCondition(): void {
    this.conditionLignes.push({ champ: this.champsCondition[0]?.code ?? 'montant_demande_ref', op: '>', valeur: null });
  }

  private conditionDepuisLignes(): any {
    if (this.conditionAvancee) return this.edition?.condition ?? null;
    const lignes = this.conditionLignes.filter(l => l.champ && l.op);
    if (!lignes.length) return null;
    return { [this.conditionGroupe]: lignes.map(l => {
      const nature = this.natureChamp(l.champ);
      let valeur = l.valeur;
      if (['vide', 'non_vide'].includes(l.op)) return { champ: l.champ, op: l.op };
      if (['dans', 'pas_dans'].includes(l.op) && typeof valeur === 'string') valeur = valeur.split(',').map((x: string) => x.trim()).filter(Boolean);
      if (['montant', 'entier'].includes(nature) && valeur !== null && valeur !== '' && !Array.isArray(valeur)) valeur = Number(valeur);
      return { champ: l.champ, op: l.op, valeur };
    }) };
  }

  enregistrerEtape(): void {
    if (!this.edition) return;
    const e: any = { ...this.edition, condition: this.conditionDepuisLignes() };
    e.regles = e.regles.map((r: RegleDesignation) => ({
      mode: r.mode, responsabilite: r.mode === 'responsabilite' ? r.responsabilite : null,
      perimetre: r.mode === 'responsabilite' ? r.perimetre : 'aucun', personne: r.mode === 'personne' ? r.personne : null,
      relation: r.mode === 'relation' ? r.relation : '',
    }));
    if (e.mode !== 'parallele') e.quorum = null;
    this.service.enregistrerEtape(e).subscribe({
      next: () => { this.edition = null; this.erreursControle = null; this.toast.success('Étape enregistrée.'); this.charger(); },
      error: err => this.toast.error(messageErreur(err)),
    });
  }

  supprimerEtape(e: Etape): void {
    if (!e.id || !confirm(`Supprimer l'étape « ${e.libelle} » ?`)) return;
    this.service.supprimerEtape(e.id).subscribe({ next: () => this.charger(), error: x => this.toast.error(messageErreur(x)) });
  }

  deplacer(index: number, delta: number): void {
    if (!this.version) return;
    const ids = this.version.etapes.map(e => e.id!);
    const cible = index + delta;
    if (cible < 0 || cible >= ids.length) return;
    [ids[index], ids[cible]] = [ids[cible], ids[index]];
    this.service.reordonner(this.version.id, ids).subscribe({ next: v => this.version = v, error: x => this.toast.error(messageErreur(x)) });
  }

  // ── Version ──────────────────────────────────────────────
  enregistrerReprise(): void {
    if (!this.version) return;
    this.service.modifierVersion(this.version.id, { reprise_apres_correction: this.version.reprise_apres_correction })
      .subscribe({ next: () => this.toast.success('Règle de reprise enregistrée.'), error: e => this.toast.error(messageErreur(e)) });
  }

  controler(): void {
    if (!this.version) return;
    this.service.controler(this.version.id).subscribe(r => {
      this.erreursControle = r.erreurs;
      if (!r.erreurs.length) this.toast.success('Aucune erreur : le circuit peut être publié.');
    });
  }

  publier(): void {
    if (!this.version || !confirm('Publier cette version ? Elle s\'appliquera à toutes les nouvelles demandes ; les demandes en cours gardent leur version.')) return;
    this.service.publier(this.version.id, this.commentairePublication).subscribe({
      next: () => { this.toast.success('Version publiée.'); this.charger(); },
      error: e => {
        this.erreursControle = e?.champs?.publication ?? null;
        this.toast.error(messageErreur(e, 'Publication impossible.'));
      },
    });
  }

  supprimerBrouillon(): void {
    if (!this.version || !confirm('Supprimer ce brouillon ?')) return;
    this.service.supprimerVersion(this.version.id).subscribe({
      next: () => this.router.navigate(['/parametres/workflows'], { queryParams: { type: this.version?.type_demande } }),
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  nouvelleVersion(): void {
    if (!this.version) return;
    this.service.nouvelleVersion(this.version.type_demande, this.version.id).subscribe({
      next: v => this.router.navigate(['/parametres/workflows', v.id]),
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  // ── Simulation ───────────────────────────────────────────
  get champsSimulation(): ChampCondition[] { return this.champsCondition.filter(c => c.code.startsWith('champ.')); }

  simuler(): void {
    if (!this.version || !this.simDemandeur) { this.toast.warning('Choisissez un demandeur.'); return; }
    const donnees: Record<string, any> = {};
    for (const [k, v] of Object.entries(this.simDonnees)) if (v !== null && v !== '') donnees[k.replace('champ.', '')] = v;
    this.service.simuler(this.version.id, this.simDemandeur, this.simMontant, donnees).subscribe({
      next: r => this.simResultat = r,
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  noms(e: EntreePlan): string { return e.valideurs.map(v => v.nom).join(', '); }
}
