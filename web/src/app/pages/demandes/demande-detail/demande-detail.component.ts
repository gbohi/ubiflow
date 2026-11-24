// src/app/pages/demandes/demande-detail/demande-detail.component.ts
//
// Fiche d'une demande : contenu (modifiable en brouillon / correction),
// pièces jointes, circuit de validation, actions du demandeur, panneau de
// validation pour le valideur (ou son délégataire), commentaires, historique.

import { Component, DestroyRef, OnInit, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import {
  Action, CLASSES_STATUT, CycleCircuit, Demande, DemandesService, MaTache, TypePiece, enregistrerFichier,
} from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import {
  ROLES_ADMIN_FINANCES, ROLES_TRESORERIE, Reglement, TresorerieService,
} from 'src/app/core/services/tresorerie/tresorerie.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';
import { ContenuDemande } from '../champs-demande/champs-demande.component';
import { PaiementModalComponent } from '../paiement-modal/paiement-modal.component';

@Component({
  selector: 'app-demande-detail',
  templateUrl: './demande-detail.component.html',
  styles: [`
    .dd-etapes { list-style: none; padding: 0; margin: 0; position: relative; }
    .dd-etapes li { position: relative; padding: 0 0 14px 30px; }
    .dd-etapes li::before { content: ''; position: absolute; left: 10px; top: 22px; bottom: 0; width: 2px; background: var(--bs-border-color); }
    .dd-etapes li:last-child::before { display: none; }
    .dd-pt { position: absolute; left: 0; top: 2px; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center;
             font-size: 12px; color: #fff; background: #adb5bd; }
    .dd-pt.approuvee { background: #2fb46c; } .dd-pt.en_cours { background: #0F3A6E; } .dd-pt.rejetee { background: #dc3545; }
    .dd-pt.retournee { background: #e8a33d; } .dd-pt.sautee, .dd-pt.annulee { background: #ced4da; }
    .dd-hist { max-height: 420px; overflow: auto; }
  `],
})
export class DemandeDetailComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);
  private readonly destroyRef = inject(DestroyRef);

  readonly classes = CLASSES_STATUT;
  readonly classesFinancier: Record<string, string> = {
    a_payer: 't-or', partiellement_payee: 't-or', payee: 't-ve', soldee: 't-ve', reversement_attendu: 't-ro',
  };
  private readonly tresorerieService = inject(TresorerieService);
  private readonly utilisateur = inject(TokenStorageService).getUser();
  readonly tresorerie = aUnRole(this.utilisateur, ROLES_TRESORERIE);
  readonly adminFinances = aUnRole(this.utilisateur, ROLES_ADMIN_FINANCES);
  @ViewChild(PaiementModalComponent) paiement!: PaiementModalComponent;
  @ViewChild('annulationReglementModal', { static: false }) annulationReglementModal?: ModalDirective;
  reglementAAnnuler: Reglement | null = null;
  motifAnnulationReglement = '';
  demande: Demande | null = null;
  contenu: ContenuDemande = { objet: '', montant_demande: null, devise: '', donnees: {} };
  /** Saisie d'une mission (copie de travail de `demande.mission`) */
  mission: Record<string, any> = {};
  erreurs: any = null;
  historique: Action[] = [];
  typesPieces: TypePiece[] = [];
  chargement = true;
  enCours = false;

  // Soumission
  @ViewChild('soumissionModal', { static: false }) soumissionModal?: ModalDirective;
  motifResoumission = '';

  // Annulation
  @ViewChild('annulationModal', { static: false }) annulationModal?: ModalDirective;
  motifAnnulation = '';

  // Validation
  tache: MaTache | null = null;
  motifValidation = '';
  montantApprouve: any = null;
  /** Champs du type que le valideur peut corriger à cette étape */
  corrections: ContenuDemande = { objet: '', montant_demande: null, devise: '', donnees: {} };

  // Pièces
  fichier: File | null = null;
  typePiece: number | null = null;
  commentaire = '';

  ngOnInit(): void {
    this.service.typesPieces().subscribe(t => this.typesPieces = t.filter(x => x.actif));
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(p => this.charger(Number(p.get('id'))));
  }

  charger(id = this.demande?.id): void {
    if (!id) return;
    this.chargement = !this.demande || this.demande.id !== id;
    this.service.demande(id).subscribe({
      next: d => {
        this.demande = d;
        this.contenu = { objet: d.objet, montant_demande: d.montant_demande ? Number(d.montant_demande) : null,
                         devise: d.devise, donnees: { ...(d.donnees ?? {}) } };
        this.mission = JSON.parse(JSON.stringify(d.mission ?? {}));
        this.tache = d.mes_taches?.[0] ?? null;
        this.montantApprouve = d.montant_approuve ?? d.montant_demande;
        this.corrections = { objet: d.objet, montant_demande: null, devise: d.devise, donnees: { ...(d.donnees ?? {}) } };
        this.chargement = false;
        this.service.historique(id).subscribe(h => this.historique = h.slice().reverse());
      },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); this.router.navigate(['/demandes']); },
    });
  }

  get estMission(): boolean { return this.demande?.type_famille === 'mission'; }
  get typeMission(): 'locale' | 'hors_pays' { return this.demande?.type_parametres?.['type_mission'] ?? 'locale'; }
  get editable(): boolean { return !!this.demande?.actions?.modifier; }
  get cycleCourant(): CycleCircuit | null { return this.demande?.circuit?.at(-1) ?? null; }
  get retourEnCours(): Action | undefined {
    return this.demande?.statut === 'a_corriger' ? this.historique.find(a => a.type === 'retour') : undefined;
  }
  get rejet(): Action | undefined {
    return this.demande?.statut === 'rejetee' ? this.historique.find(a => a.type === 'rejet') : undefined;
  }
  get peutModifierMontant(): boolean { return !!this.tache?.champs_modifiables?.includes('montant_approuve'); }
  get champsCorrigeables() {
    const codes = this.tache?.champs_modifiables ?? [];
    return (this.demande?.champs ?? []).filter(c => codes.includes(c.code));
  }

  // ── Contenu ──────────────────────────────────────────────
  private enregistrer$() {
    return this.service.modifier(this.demande!.id, {
      objet: this.contenu.objet, montant_demande: this.contenu.montant_demande, donnees: this.contenu.donnees,
      ...(this.estMission ? { mission: this.mission } : {}),
    });
  }

  enregistrer(): void {
    if (!this.demande || this.enCours) return;
    this.enCours = true;
    this.erreurs = null;
    this.enregistrer$().subscribe({
      next: () => { this.enCours = false; this.toast.success('Modifications enregistrées.'); this.charger(); },
      error: e => { this.enCours = false; this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e)); },
    });
  }

  // ── Soumission ───────────────────────────────────────────
  ouvrirSoumission(): void {
    if (!this.demande) return;
    this.erreurs = null;
    this.motifResoumission = '';
    this.soumissionModal?.show();
  }

  /** Enregistre la saisie en cours puis soumet (ou resoumet) la demande */
  soumettre(): void {
    if (!this.demande || this.enCours) return;
    this.enCours = true;
    const echec = (e: any) => {
      this.enCours = false;
      this.erreurs = e?.champs ?? null;
      const circuit = e?.champs?.circuit;
      this.toast.error(Array.isArray(circuit) ? circuit.join(' ') : messageErreur(e));
    };
    this.enregistrer$().subscribe({
      next: () => this.service.soumettre(this.demande!.id, this.motifResoumission).subscribe({
        next: d => {
          this.enCours = false;
          this.soumissionModal?.hide();
          this.toast.success(`Demande ${d.reference} soumise.`);
          this.charger();
        },
        error: e => { this.soumissionModal?.hide(); echec(e); },
      }),
      error: e => { this.soumissionModal?.hide(); echec(e); },
    });
  }

  // ── PDF de présentation ──────────────────────────────────
  pdfEnCours = false;
  telechargerPdf(): void {
    if (!this.demande || this.pdfEnCours) return;
    this.pdfEnCours = true;
    this.service.pdf(this.demande.id).subscribe({
      next: b => { this.pdfEnCours = false; enregistrerFichier(b, `${this.demande?.reference || 'brouillon-' + this.demande?.id}.pdf`); },
      error: e => { this.pdfEnCours = false; this.toast.error(messageErreur(e)); },
    });
  }

  // ── Paiements ────────────────────────────────────────────
  ouvrirAnnulationReglement(r: Reglement): void {
    this.reglementAAnnuler = r;
    this.motifAnnulationReglement = '';
    this.annulationReglementModal?.show();
  }

  annulerReglement(): void {
    if (!this.reglementAAnnuler || this.enCours) return;
    this.enCours = true;
    this.tresorerieService.annulerReglement(this.reglementAAnnuler.id, this.motifAnnulationReglement).subscribe({
      next: () => { this.enCours = false; this.annulationReglementModal?.hide(); this.toast.success('Paiement annulé.'); this.charger(); },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e)); },
    });
  }

  // ── Autres actions du demandeur ──────────────────────────
  supprimer(): void {
    if (!this.demande || !confirm('Supprimer ce brouillon ?')) return;
    this.service.supprimer(this.demande.id).subscribe({
      next: () => { this.toast.success('Brouillon supprimé.'); this.router.navigate(['/demandes']); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  annuler(): void {
    if (!this.demande || !this.motifAnnulation.trim()) return;
    this.service.annuler(this.demande.id, this.motifAnnulation.trim()).subscribe({
      next: () => { this.annulationModal?.hide(); this.toast.success('Demande annulée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  dupliquer(): void {
    if (!this.demande) return;
    this.service.dupliquer(this.demande.id).subscribe({
      next: d => { this.toast.success('Nouvelle demande créée à partir de celle-ci.'); this.router.navigate(['/demandes', d.id]); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  // ── Validation ───────────────────────────────────────────
  agir(action: 'approuver' | 'rejeter' | 'retourner'): void {
    if (!this.tache || this.enCours) return;
    const motif = this.motifValidation.trim();
    if (action !== 'approuver' && !motif) { this.toast.warning('Le motif est obligatoire.'); return; }
    if (action === 'rejeter' && !confirm('Rejeter définitivement cette demande ?')) return;
    const modifications: any = {};
    if (action === 'approuver' && this.peutModifierMontant
        && Number(this.montantApprouve) !== Number(this.demande?.montant_approuve ?? this.demande?.montant_demande)) {
      modifications.montant_approuve = this.montantApprouve;
    }
    if (action === 'approuver') {
      for (const c of this.champsCorrigeables) {
        const avant = this.demande?.donnees?.[c.code], apres = this.corrections.donnees[c.code];
        if (String(avant ?? '') !== String(apres ?? '')) modifications[c.code] = apres;
      }
    }
    this.enCours = true;
    this.service.agir(this.tache.id, action, motif, Object.keys(modifications).length ? modifications : undefined).subscribe({
      next: r => {
        this.enCours = false;
        this.motifValidation = '';
        const libelles = { approuver: 'Validation enregistrée.', rejeter: 'Demande rejetée.', retourner: 'Demande retournée au demandeur.' };
        this.toast.success(`${libelles[action]} Statut : ${r.statut_libelle}.`);
        this.charger();
      },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e)); },
    });
  }

  // ── Pièces jointes ───────────────────────────────────────
  choisirFichier(evt: Event): void { this.fichier = (evt.target as HTMLInputElement).files?.[0] ?? null; }

  ajouterPiece(champ: HTMLInputElement): void {
    if (!this.demande || !this.fichier) return;
    this.service.ajouterDocument(this.demande.id, this.fichier, this.typePiece).subscribe({
      next: () => { this.toast.success('Pièce ajoutée.'); this.fichier = null; champ.value = ''; this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  retirerPiece(doc: { id: number; nom_origine: string; version_numero: number | null }): void {
    if (!this.demande) return;
    let motif = '';
    if (doc.version_numero !== null || this.demande.reference) {
      motif = prompt(`Motif du retrait de « ${doc.nom_origine} » (la pièce reste conservée) :`) ?? '';
      if (!motif.trim()) return;
    } else if (!confirm(`Supprimer « ${doc.nom_origine} » ?`)) {
      return;
    }
    this.service.retirerDocument(this.demande.id, doc.id, motif).subscribe({
      next: () => { this.toast.success('Pièce retirée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  telecharger(doc: { id: number; nom_origine: string }): void {
    if (!this.demande) return;
    this.service.telechargerDocument(this.demande.id, doc.id).subscribe({
      next: b => enregistrerFichier(b, doc.nom_origine),
      error: e => this.toast.error(messageErreur(e, 'Téléchargement impossible.')),
    });
  }

  taille(o: number): string { return o > 1024 * 1024 ? `${(o / 1024 / 1024).toFixed(1)} Mo` : `${Math.ceil(o / 1024)} Ko`; }

  // ── Commentaires ─────────────────────────────────────────
  commenter(): void {
    if (!this.demande || !this.commentaire.trim()) return;
    this.service.commenter(this.demande.id, this.commentaire.trim()).subscribe({
      next: () => { this.commentaire = ''; this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  iconeAction(type: string): string {
    return ({ creation: 'ri-file-add-line', soumission: 'ri-send-plane-line', resoumission: 'ri-send-plane-line',
              approbation: 'ri-check-line', auto_approbation: 'ri-check-double-line', rejet: 'ri-close-circle-line',
              retour: 'ri-arrow-go-back-line', commentaire: 'ri-chat-3-line', annulation: 'ri-forbid-line',
              saut: 'ri-skip-forward-line', approbation_finale: 'ri-checkbox-circle-line', correction: 'ri-edit-line',
              reaffectation: 'ri-shuffle-line', document: 'ri-attachment-2', duplication: 'ri-file-copy-line',
              reresolution: 'ri-refresh-line' } as Record<string, string>)[type] ?? 'ri-information-line';
  }
}
