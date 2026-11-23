// src/app/pages/parametres/user/organisation-collaborateur/organisation-collaborateur.component.ts
//
// Hiérarchie d'un collaborateur (fiche Utilisateurs) : situation à une date
// (N+1 et N+2 résolus, responsabilités), historique des N+1, réaffectation
// exceptionnelle motivée et situation de véhicule. Chaque modification est
// enregistrée immédiatement (indépendante du bouton « Enregistrer » de la fiche).

import { Component, Input, OnChanges, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { forkJoin } from 'rxjs';
import {
  AffectationHierarchique, OrganisationCollaborateur, OrganisationService, SituationVehicule,
  aujourdhui, messageErreur,
} from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-organisation-collaborateur',
  templateUrl: './organisation-collaborateur.component.html',
})
export class OrganisationCollaborateurComponent implements OnChanges {
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);

  @Input({ required: true }) userId!: number;
  /** Fenêtre « Détails » : consultation seulement */
  @Input() lectureSeule = false;

  readonly aujourdhui = aujourdhui();
  date = aujourdhui();
  situation: OrganisationCollaborateur | null = null;
  hierarchie: AffectationHierarchique[] = [];
  vehicules: SituationVehicule[] = [];
  collaborateurs: { id: number; libelle: string }[] = [];
  chargement = false;

  ligneN1: AffectationHierarchique | null = null;
  reaffectation: { mode: string; responsable: number | null; date_effet: string; motif: string } | null = null;
  ligneVehicule: SituationVehicule | null = null;

  readonly libellesSource: Record<string, string> = {
    designe: 'désigné', departement: 'responsable du département',
    departement_parent: 'responsable du département parent', introuvable: 'introuvable',
  };

  ngOnChanges(): void {
    if (!this.userId) return;
    this.charger();
    if (!this.lectureSeule && !this.collaborateurs.length) {
      this.organisation.collaborateursTous().subscribe(u => this.collaborateurs = (u ?? [])
        .filter(x => x.is_active && x.id !== this.userId)
        .map(x => ({ id: x.id, libelle: `${x.nom} ${x.prenom} (${x.username})` })));
    }
  }

  charger(): void {
    this.chargement = true;
    forkJoin({
      situation: this.organisation.organisation(this.userId, this.date),
      hierarchie: this.organisation.affectationsHierarchiques(this.userId),
      vehicules: this.organisation.situationsVehicule(this.userId),
    }).subscribe({
      next: r => {
        this.situation = r.situation;
        this.hierarchie = r.hierarchie;
        this.vehicules = r.vehicules;
        this.chargement = false;
      },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  enCours(l: { date_debut: string; date_fin?: string | null }): boolean {
    return l.date_debut <= this.aujourdhui && (!l.date_fin || l.date_fin >= this.aujourdhui);
  }

  // ── N+1 ──────────────────────────────────────────────────
  nouvelleLigneN1(): void {
    this.reaffectation = null;
    this.ligneN1 = { user: this.userId, mode: 'automatique', responsable: null, date_debut: this.aujourdhui,
                     date_fin: null, motif: '' };
  }

  modifierLigneN1(l: AffectationHierarchique): void {
    this.reaffectation = null;
    this.ligneN1 = { ...l };
  }

  enregistrerLigneN1(): void {
    const l = this.ligneN1;
    if (!l) return;
    if (l.mode === 'designe' && !l.responsable) { this.toast.warning('Choisissez le N+1 désigné.'); return; }
    const donnees: AffectationHierarchique = {
      id: l.id, user: this.userId, mode: l.mode, responsable: l.mode === 'designe' ? Number(l.responsable) : null,
      date_debut: l.date_debut, date_fin: l.date_fin || null, motif: l.motif || '',
    };
    this.organisation.enregistrerAffectationHierarchique(donnees).subscribe({
      next: () => { this.toast.success('Affectation hiérarchique enregistrée.'); this.ligneN1 = null; this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  supprimerLigneN1(l: AffectationHierarchique): void {
    if (!l.id || !confirm('Supprimer cette ligne de l\'historique ? Pour un changement de N+1, renseignez plutôt une date de fin.')) return;
    this.organisation.supprimerAffectationHierarchique(l.id).subscribe({
      next: () => { this.toast.success('Ligne supprimée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  ouvrirReaffectation(): void {
    this.ligneN1 = null;
    this.reaffectation = { mode: 'designe', responsable: null, date_effet: this.aujourdhui, motif: '' };
  }

  reaffecter(): void {
    const r = this.reaffectation;
    if (!r) return;
    if (!r.motif.trim()) { this.toast.warning('Le motif est obligatoire.'); return; }
    if (r.mode === 'designe' && !r.responsable) { this.toast.warning('Choisissez le nouveau N+1.'); return; }
    this.organisation.reaffecterN1(this.userId, {
      mode: r.mode, responsable: r.mode === 'designe' ? Number(r.responsable) : null,
      date_effet: r.date_effet, motif: r.motif.trim(),
    }).subscribe({
      next: res => {
        this.toast.success(`N+1 réaffecté : ${res.n_plus_1.personne?.nom_complet ?? 'introuvable'}.`);
        this.reaffectation = null;
        this.charger();
      },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  // ── Véhicule ─────────────────────────────────────────────
  nouvelleLigneVehicule(): void {
    this.ligneVehicule = { user: this.userId, possede_vehicule: true, date_debut: this.aujourdhui, date_fin: null, commentaire: '' };
  }

  modifierLigneVehicule(l: SituationVehicule): void { this.ligneVehicule = { ...l }; }

  enregistrerLigneVehicule(): void {
    const l = this.ligneVehicule;
    if (!l) return;
    this.organisation.enregistrerSituationVehicule({
      id: l.id, user: this.userId, possede_vehicule: !!l.possede_vehicule, date_debut: l.date_debut,
      date_fin: l.date_fin || null, commentaire: l.commentaire || '',
    }).subscribe({
      next: () => { this.toast.success('Situation de véhicule enregistrée.'); this.ligneVehicule = null; this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  supprimerLigneVehicule(l: SituationVehicule): void {
    if (!l.id || !confirm('Supprimer cette ligne ?')) return;
    this.organisation.supprimerSituationVehicule(l.id).subscribe({
      next: () => { this.toast.success('Ligne supprimée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }
}
