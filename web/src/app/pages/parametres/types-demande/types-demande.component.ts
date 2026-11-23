// src/app/pages/parametres/types-demande/types-demande.component.ts
//
// Types de demande : fiche (référence, montant, annulation…), champs du
// formulaire et pièces exigées. Un type « simple » se crée sans développement.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { ChampType, DemandesService, ExigencePiece, TypeDemande, TypePiece } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-types-demande',
  templateUrl: './types-demande.component.html',
})
export class TypesDemandeComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);

  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;

  types: TypeDemande[] = [];
  typesPieces: TypePiece[] = [];
  courant: TypeDemande | null = null;
  fiche: Partial<TypeDemande> = {};
  champ: Partial<ChampType> | null = null;
  optionsTexte = '';
  exigence: Partial<ExigencePiece> | null = null;

  readonly natures = [
    ['texte', 'Texte'], ['texte_long', 'Texte long'], ['entier', 'Nombre entier'], ['montant', 'Montant'],
    ['date', 'Date'], ['datetime', 'Date et heure'], ['liste', 'Liste de choix'], ['booleen', 'Oui / non'],
    ['collaborateur', 'Collaborateur'],
  ];
  readonly moments = [['soumission', 'À la soumission'], ['etape', 'À une étape'], ['paiement', 'Au paiement'], ['cloture', 'À la clôture']];

  ngOnInit(): void {
    this.charger();
    this.service.typesPieces().subscribe(t => this.typesPieces = t);
  }

  charger(selection?: number): void {
    this.service.types(true).subscribe({
      next: t => {
        this.types = t;
        const id = selection ?? this.courant?.id;
        this.courant = t.find(x => x.id === id) ?? null;
      },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  // ── Fiche ────────────────────────────────────────────────
  nouveau(): void {
    this.fiche = { code: '', libelle: '', description: '', prefixe_reference: '', avec_montant: true, actif: true,
                   paiement_fractionne_autorise: true, annulation_demandeur: ['en_validation', 'a_corriger'], icone: 'ri-file-text-line' };
    this.ficheModal?.show();
  }

  modifier(t: TypeDemande): void { this.fiche = { ...t }; this.ficheModal?.show(); }

  basculerAnnulation(statut: string): void {
    const l = new Set(this.fiche.annulation_demandeur ?? []);
    l.has(statut) ? l.delete(statut) : l.add(statut);
    this.fiche.annulation_demandeur = [...l];
  }

  enregistrer(): void {
    this.service.enregistrerType(this.fiche).subscribe({
      next: t => { this.ficheModal?.hide(); this.toast.success('Type de demande enregistré.'); this.charger(t.id); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  // ── Champs ───────────────────────────────────────────────
  nouveauChamp(): void {
    if (!this.courant) return;
    this.champ = { type_demande: this.courant.id, code: '', libelle: '', nature: 'texte', obligatoire: false, options: [],
                   ordre: (this.courant.champs?.length ?? 0) + 1, aide: '', sensible: false, utilisable_en_condition: false, actif: true };
    this.optionsTexte = '';
  }

  modifierChamp(c: ChampType): void { this.champ = { ...c }; this.optionsTexte = (c.options ?? []).join('\n'); }

  enregistrerChamp(): void {
    if (!this.champ) return;
    this.champ.options = this.optionsTexte.split('\n').map(o => o.trim()).filter(Boolean);
    this.service.enregistrerChamp(this.champ).subscribe({
      next: () => { this.champ = null; this.toast.success('Champ enregistré.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  supprimerChamp(c: ChampType): void {
    if (!c.id || !confirm(`Supprimer le champ « ${c.libelle} » ? Les demandes existantes gardent leurs valeurs.`)) return;
    this.service.supprimerChamp(c.id).subscribe({ next: () => this.charger(), error: e => this.toast.error(messageErreur(e)) });
  }

  // ── Pièces exigées ───────────────────────────────────────
  nouvelleExigence(): void {
    if (!this.courant) return;
    this.exigence = { type_demande: this.courant.id, type_piece: this.typesPieces[0]?.id, moment: 'soumission', etape_code: '', obligatoire: true };
  }

  enregistrerExigence(): void {
    if (!this.exigence) return;
    this.service.enregistrerExigence(this.exigence).subscribe({
      next: () => { this.exigence = null; this.toast.success('Pièce exigée enregistrée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  supprimerExigence(e: ExigencePiece): void {
    if (!e.id || !confirm('Supprimer cette exigence ?')) return;
    this.service.supprimerExigence(e.id).subscribe({ next: () => this.charger(), error: x => this.toast.error(messageErreur(x)) });
  }

  libelleNature(n: string): string { return this.natures.find(x => x[0] === n)?.[1] ?? n; }
}
