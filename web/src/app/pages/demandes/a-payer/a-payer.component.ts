// src/app/pages/demandes/a-payer/a-payer.component.ts
//
// File à payer (§8.1) : demandes approuvées à payer ou partiellement payées,
// les plus anciennes d'abord ; filtres, export Excel, saisie des paiements.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { Subject, debounceTime } from 'rxjs';
import {
  CLASSES_STATUT, Demande, DemandesService, TypeDemande, iconeType, teinteType,
} from 'src/app/core/services/demandes/demandes.service';
import { TresorerieService } from 'src/app/core/services/tresorerie/tresorerie.service';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { PaiementModalComponent } from '../paiement-modal/paiement-modal.component';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-a-payer',
  templateUrl: './a-payer.component.html',
})
export class APayerComponent implements OnInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Référence', champ: 'reference' }, { libelle: 'Type', champ: 'type_libelle' },
    { libelle: 'Demandeur', champ: 'demandeur_nom' }, { libelle: 'Objet', champ: 'objet' },
    { libelle: 'Approuvée le', champ: 'approuvee_le', format: 'date' },
    { libelle: 'Approuvé', champ: 'montant_approuve', format: 'montant', devise: 'devise' },
    { libelle: 'Payé', champ: 'montant_paye', format: 'montant', devise: 'devise' },
    { libelle: 'Reste à payer', champ: d => this.reste(d), format: 'montant', devise: 'devise' },
    { libelle: 'Statut financier', champ: 'statut_financier_libelle' },
  ];
  get paramsExport(): Record<string, any> { return { ...this.filtres }; }

  private readonly service = inject(TresorerieService);
  private readonly demandes = inject(DemandesService);
  private readonly organisation = inject(OrganisationService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);

  @ViewChild(PaiementModalComponent) paiement?: PaiementModalComponent;

  readonly classes = CLASSES_STATUT;
  readonly icone = iconeType;
  readonly teinte = teinteType;
  types: TypeDemande[] = [];
  departements: any[] = [];
  agences: any[] = [];
  filtres = { type_demande: null as number | null, departement: null as number | null, agence: null as number | null,
              du: '', au: '', montant_min: '', montant_max: '', search: '' };
  lignes: Demande[] = [];
  total = 0;
  page = 1;
  chargement = true;
  private readonly recherche$ = new Subject<void>();

  ngOnInit(): void {
    this.demandes.types(true).subscribe(t => this.types = t.filter(x => x.avec_montant));
    this.organisation.departementsTous().subscribe(d => this.departements = d ?? []);
    this.organisation.agencesToutes().subscribe(a => this.agences = a ?? []);
    this.recherche$.pipe(debounceTime(300)).subscribe(() => this.charger(1));
    this.charger();
  }

  charger(page = this.page): void {
    this.page = page;
    this.chargement = true;
    this.service.aPayer({ ...this.filtres, page }).subscribe({
      next: r => { this.lignes = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  rechercher(): void { this.recherche$.next(); }

  reinitialiser(): void {
    this.filtres = { type_demande: null, departement: null, agence: null, du: '', au: '', montant_min: '', montant_max: '', search: '' };
    this.charger(1);
  }

  get filtresActifs(): boolean {
    const f = this.filtres;
    return !!(f.type_demande || f.departement || f.agence || f.du || f.au || f.montant_min || f.montant_max || f.search);
  }

  alertesTexte(d: Demande): string { return (d.alertes ?? []).map(a => a.message).join('\n'); }

  reste(d: Demande): number { return Number(d.montant_approuve ?? 0) - Number(d.montant_paye ?? 0); }

  payer(d: Demande, e: Event): void {
    e.stopPropagation();
    const type = this.types.find(t => t.id === d.type_demande);
    this.paiement?.ouvrir(d, type?.paiement_fractionne_autorise ?? true);
  }

  ouvrir(d: Demande): void { this.router.navigate(['/demandes', d.id]); }
}
