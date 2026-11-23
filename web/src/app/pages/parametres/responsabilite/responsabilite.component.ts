// src/app/pages/parametres/responsabilite/responsabilite.component.ts
//
// Responsabilités (DG, DAF, Chef comptable, Responsable de département…) et
// leurs titulaires datés. Ce sont elles, et non les fonctions RH, qui
// désignent les valideurs dans les circuits.

import { Component, DestroyRef, OnInit, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import {
  AffectationResponsabilite, OrganisationService, Responsabilite, aujourdhui, messageErreur,
} from 'src/app/core/services/organisation/organisation.service';

const PORTEES = [
  { valeur: 'globale', libelle: "Toute l'entreprise" },
  { valeur: 'departement', libelle: 'Un département' },
  { valeur: 'agence', libelle: 'Une agence' },
];

@Component({
  selector: 'app-responsabilite',
  templateUrl: './responsabilite.component.html',
})
export class ResponsabiliteComponent implements OnInit {
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);
  private readonly destroyRef = inject(DestroyRef);

  readonly portees = PORTEES;
  readonly aujourdhui = aujourdhui();

  responsabilites: Responsabilite[] = [];
  chargement = true;
  recherche = '';
  private readonly recherche$ = new Subject<string>();

  // Fiche responsabilité
  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;
  fiche: Responsabilite = this.ficheVide();
  enregistrement = false;

  // Suppression
  @ViewChild('suppressionModal', { static: false }) suppressionModal?: ModalDirective;
  aSupprimer: Responsabilite | null = null;

  // Titulaires
  @ViewChild('titulairesModal', { static: false }) titulairesModal?: ModalDirective;
  courante: Responsabilite | null = null;
  affectations: AffectationResponsabilite[] = [];
  chargementTitulaires = false;
  ligne: AffectationResponsabilite | null = null;
  collaborateurs: any[] = [];
  departements: any[] = [];
  agences: any[] = [];

  ngOnInit(): void {
    this.recherche$.pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.charger());
    this.charger();
    this.organisation.collaborateursTous().pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(u => this.collaborateurs = (u ?? []).filter(x => x.is_active).map(x => ({
        id: x.id, libelle: `${x.nom} ${x.prenom} (${x.username})`,
      })));
    this.organisation.departementsTous().pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(d => this.departements = d ?? []);
    this.organisation.agencesToutes().pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(a => this.agences = a ?? []);
  }

  charger(): void {
    this.chargement = true;
    this.organisation.responsabilites(this.recherche.trim()).subscribe({
      next: r => { this.responsabilites = r; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  rechercher(): void { this.recherche$.next(this.recherche); }

  libellePortee(p: string): string { return PORTEES.find(x => x.valeur === p)?.libelle ?? p; }

  // ── Fiche ────────────────────────────────────────────────
  private ficheVide(): Responsabilite {
    return { code: '', libelle: '', portee: 'globale', multiple: false, actif: true };
  }

  nouvelle(): void {
    this.fiche = this.ficheVide();
    this.ficheModal?.show();
  }

  modifier(r: Responsabilite): void {
    this.fiche = { ...r };
    this.ficheModal?.show();
  }

  enregistrer(): void {
    if (!this.fiche.code.trim() || !this.fiche.libelle.trim() || this.enregistrement) return;
    this.enregistrement = true;
    const donnees: any = { ...this.fiche };
    delete donnees.nb_titulaires; delete donnees.portee_libelle; delete donnees.systeme;
    this.organisation.enregistrerResponsabilite(donnees).subscribe({
      next: () => {
        this.enregistrement = false;
        this.toast.success(this.fiche.id ? 'Responsabilité mise à jour.' : 'Responsabilité ajoutée.');
        this.ficheModal?.hide();
        this.charger();
      },
      error: e => { this.enregistrement = false; this.toast.error(messageErreur(e)); },
    });
  }

  demanderSuppression(r: Responsabilite): void {
    this.aSupprimer = r;
    this.suppressionModal?.show();
  }

  supprimer(): void {
    if (!this.aSupprimer?.id) return;
    this.organisation.supprimerResponsabilite(this.aSupprimer.id).subscribe({
      next: () => { this.toast.success('Responsabilité supprimée.'); this.suppressionModal?.hide(); this.charger(); },
      error: e => { this.toast.error(messageErreur(e)); this.suppressionModal?.hide(); },
    });
  }

  // ── Titulaires ───────────────────────────────────────────
  ouvrirTitulaires(r: Responsabilite): void {
    this.courante = r;
    this.ligne = null;
    this.affectations = [];
    this.titulairesModal?.show();
    this.chargerTitulaires();
  }

  private chargerTitulaires(): void {
    if (!this.courante?.id) return;
    this.chargementTitulaires = true;
    this.organisation.affectationsResponsabilite({ responsabilite: this.courante.id }).subscribe({
      next: a => { this.affectations = a; this.chargementTitulaires = false; },
      error: e => { this.chargementTitulaires = false; this.toast.error(messageErreur(e)); },
    });
  }

  estEnCours(a: AffectationResponsabilite): boolean {
    return a.date_debut <= this.aujourdhui && (!a.date_fin || a.date_fin >= this.aujourdhui);
  }

  perimetre(a: AffectationResponsabilite): string {
    return a.departement_libelle || a.agence_libelle || "Toute l'entreprise";
  }

  nouvelleLigne(): void {
    if (!this.courante?.id) return;
    this.ligne = { user: null as any, responsabilite: this.courante.id, departement: null, agence: null,
                   date_debut: this.aujourdhui, date_fin: null, motif: '' };
  }

  modifierLigne(a: AffectationResponsabilite): void {
    this.ligne = { ...a };
  }

  enregistrerLigne(): void {
    const l = this.ligne;
    if (!l || !l.user || !l.date_debut) { this.toast.warning('Choisissez le collaborateur et la date de début.'); return; }
    const donnees: AffectationResponsabilite = {
      id: l.id, user: Number(l.user), responsabilite: l.responsabilite,
      departement: this.courante?.portee === 'departement' ? Number(l.departement) || null : null,
      agence: this.courante?.portee === 'agence' ? Number(l.agence) || null : null,
      date_debut: l.date_debut, date_fin: l.date_fin || null, motif: l.motif || '',
    };
    this.organisation.enregistrerAffectationResponsabilite(donnees).subscribe({
      next: () => { this.toast.success('Titulaire enregistré.'); this.ligne = null; this.chargerTitulaires(); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  supprimerLigne(a: AffectationResponsabilite): void {
    if (!a.id || !confirm(`Supprimer cette ligne de ${a.user_nom} ? Pour mettre fin à une responsabilité, renseignez plutôt sa date de fin.`)) return;
    this.organisation.supprimerAffectationResponsabilite(a.id).subscribe({
      next: () => { this.toast.success('Ligne supprimée.'); this.chargerTitulaires(); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }
}
