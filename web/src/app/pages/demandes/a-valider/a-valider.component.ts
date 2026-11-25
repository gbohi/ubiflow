// src/app/pages/demandes/a-valider/a-valider.component.ts
//
// Validations en attente (les miennes et celles reçues par délégation) et
// historique de mes validations.

import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { DemandesService, Tache, TypeDemande, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-a-valider',
  templateUrl: './a-valider.component.html',
})
export class AValiderComponent implements OnInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Référence', champ: 'demande.reference' }, { libelle: 'Type', champ: 'demande.type_libelle' },
    { libelle: 'Demandeur', champ: 'demande.demandeur' }, { libelle: 'Objet', champ: 'demande.objet' },
    { libelle: 'Montant', champ: 'demande.montant_demande', format: 'montant', devise: 'demande.devise' },
    { libelle: 'Soumise le', champ: 'demande.soumise_le', format: 'dateheure' }, { libelle: 'Étape', champ: 'etape' },
    { libelle: 'Valideur', champ: t => t.valideur_nom + (t.pour_compte_de ? ` (pour ${t.pour_compte_de})` : '') },
    { libelle: 'Ouverte le', champ: 'ouverte_le', format: 'dateheure' },
    { libelle: 'Décision', champ: t => this.decisions[t.decision] ?? '' }, { libelle: 'Traitée le', champ: 'traitee_le', format: 'dateheure' },
  ];
  get paramsExport(): Record<string, any> { return { etat: this.onglet, type_demande: this.typeDemande, du: this.du, au: this.au, search: this.recherche.trim() }; }

  private readonly service = inject(DemandesService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);

  onglet: 'en_attente' | 'faite' = 'en_attente';
  readonly icone = iconeType;
  readonly teinte = teinteType;
  types: TypeDemande[] = [];
  typeDemande: number | null = null;
  /** Date de soumission de la demande */
  du = '';
  au = '';
  recherche = '';
  private minuterie: any;
  taches: Tache[] = [];
  total = 0;
  page = 1;
  chargement = true;

  readonly decisions: Record<string, string> = { approuvee: 'Approuvée', rejetee: 'Rejetée', retournee: 'Retournée' };
  readonly classesDecision: Record<string, string> = { approuvee: 't-ve', rejetee: 't-ro', retournee: 't-or' };

  ngOnInit(): void {
    this.service.types(true).subscribe(t => this.types = t);
    this.charger();
  }

  filtrer(): void { this.page = 1; this.charger(); }

  rechercher(): void { clearTimeout(this.minuterie); this.minuterie = setTimeout(() => this.filtrer(), 300); }

  get filtresActifs(): boolean { return !!(this.recherche || this.typeDemande || this.du || this.au); }

  effacerFiltres(): void { this.recherche = ''; this.typeDemande = null; this.du = ''; this.au = ''; this.filtrer(); }

  changer(onglet: 'en_attente' | 'faite'): void { this.onglet = onglet; this.page = 1; this.charger(); }

  charger(): void {
    this.chargement = true;
    this.service.taches(this.onglet, this.page, { type_demande: this.typeDemande, du: this.du, au: this.au, search: this.recherche.trim() }).subscribe({
      next: r => { this.taches = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  pageChangee(e: { page: number }): void { this.page = e.page; this.charger(); }

  ouvrir(t: Tache): void { this.router.navigate(['/demandes', t.demande.id]); }

  depuis(d: string | null): string {
    if (!d) return '—';
    const jours = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
    return jours <= 0 ? "aujourd'hui" : jours === 1 ? 'hier' : `${jours} jours`;
  }
}
