// src/app/pages/parametres/baremes/baremes.component.ts
//
// Barèmes datés (§3.6) : per diem, tarifs kilométriques, transport par ville,
// forfait hors pays, taux de change, devise de référence. Un changement crée
// une nouvelle ligne avec sa date d'effet ; seules les lignes futures se suppriment.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import {
  BaremesService, CodeBareme, LigneBareme, ParametreSysteme, Ville,
} from 'src/app/core/services/baremes/baremes.service';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

interface Onglet { code: CodeBareme | 'devise'; libelle: string; icone: string; aide: string; }

@Component({
  selector: 'app-baremes',
  templateUrl: './baremes.component.html',
})
export class BaremesComponent implements OnInit {
  private readonly service = inject(BaremesService);
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);
  private readonly tokens = inject(TokenStorageService);

  readonly onglets: Onglet[] = [
    { code: 'per-diem', libelle: 'Per diem', icone: 'ri-calendar-event-line',
      aide: 'Indemnité journalière par type de mission et catégorie de salarié.' },
    { code: 'kilometrique', libelle: 'Tarifs kilométriques', icone: 'ri-roadster-line',
      aide: 'Montant par km pour les missions locales en véhicule personnel (catégorie vide = toutes).' },
    { code: 'transport-ville', libelle: 'Transport par ville', icone: 'ri-bus-line',
      aide: 'Missions locales sans véhicule personnel : montant aller-retour par ville de destination, identique pour toutes les catégories.' },
    { code: 'forfait-hors-pays', libelle: 'Forfait hors pays', icone: 'ri-flight-takeoff-line',
      aide: "Missions hors pays : forfait de transport pour se rendre à l'aéroport (ajustable sur la demande avec justification)." },
    { code: 'taux-change', libelle: 'Taux de change', icone: 'ri-exchange-line',
      aide: '1 unité de la devise = taux × devise de référence.' },
    { code: 'devise', libelle: 'Devise de référence', icone: 'ri-money-dollar-circle-line',
      aide: 'Devise des totaux, des conditions de montant et des rapports.' },
  ];
  onglet: Onglet = this.onglets[0];
  lignes: LigneBareme[] = [];
  historique = false;
  chargement = false;
  categories: any[] = [];
  villes: Ville[] = [];
  parametres: ParametreSysteme | null = null;
  deviseSaisie = '';
  readonly ecriture: boolean;
  readonly aujourdhui = new Date().toISOString().slice(0, 10);

  @ViewChild('ligneModal', { static: false }) ligneModal?: ModalDirective;
  fiche: Partial<LigneBareme> = {};
  erreurs: any = null;
  enCours = false;

  constructor() {
    this.ecriture = aUnRole(this.tokens.getUser(), ['super_admin', 'admin', 'admin_finances']);
  }

  ngOnInit(): void {
    this.organisation.categoriesToutes().subscribe(c => this.categories = c ?? []);
    this.service.villes({ pays_code: 'CI' }).subscribe(v => this.villes = v);
    this.service.parametres().subscribe(p => { this.parametres = p; this.deviseSaisie = p.devise_reference; });
    this.charger();
  }

  /** Export : colonnes de l'onglet affiché */
  get colonnesExport(): ColonneExport[] {
    return [
      { libelle: 'Barème', champ: (l: LigneBareme) => this.cle(l) },
      { libelle: 'Valeur', champ: (l: LigneBareme) => Number(this.valeur(l)), format: 'montant' },
      { libelle: 'Unité', champ: (l: LigneBareme) => this.unite(l) },
      { libelle: "Date d'effet", champ: 'date_effet', format: 'date' },
      { libelle: 'Valeur précédente', champ: (l: LigneBareme) => l.precedente ? `${l.precedente.valeur} (depuis le ${new Date(l.precedente.date_effet).toLocaleDateString('fr-FR')})` : '' },
      { libelle: 'État', champ: (l: LigneBareme) => this.etat(l).libelle },
      { libelle: 'Motif', champ: 'motif' }, { libelle: 'Modifié par', champ: (l: LigneBareme) => l.modifie_par_nom || 'Système' },
      { libelle: 'Modifié le', champ: 'modifie_le', format: 'dateheure' },
    ];
  }

  get ref(): string { return this.parametres?.devise_reference ?? 'XOF'; }

  choisir(o: Onglet): void { this.onglet = o; this.charger(); }

  charger(): void {
    if (this.onglet.code === 'devise') return;
    this.chargement = true;
    this.service.lignes(this.onglet.code).subscribe({
      next: l => { this.lignes = l; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  /** Lignes affichées : en vigueur et futures (ou tout l'historique) */
  get affichees(): LigneBareme[] {
    return this.historique ? this.lignes : this.lignes.filter(l => l.en_vigueur || l.date_effet > this.aujourdhui);
  }

  etat(l: LigneBareme): { libelle: string; classe: string } {
    if (l.date_effet > this.aujourdhui) return { libelle: 'À venir', classe: 'lst-etat' };
    return l.en_vigueur ? { libelle: 'En vigueur', classe: 'lst-etat ok' } : { libelle: 'Remplacée', classe: 'lst-etat ko' };
  }

  cle(l: LigneBareme): string {
    switch (this.onglet.code) {
      case 'per-diem': return `${l.type_mission_libelle} · ${l.categorie_libelle}`;
      case 'kilometrique': return l.categorie_libelle ?? '';
      case 'transport-ville': return l.ville_libelle ?? '';
      case 'taux-change': return `1 ${l.devise}`;
      default: return "Trajet vers l'aéroport";
    }
  }

  valeur(l: LigneBareme): string { return this.onglet.code === 'taux-change' ? (l.taux ?? '') : (l.montant ?? ''); }
  unite(l: LigneBareme): string {
    return this.onglet.code === 'taux-change' ? this.ref : (l.devise ?? '') + (this.onglet.code === 'kilometrique' ? ' / km' : '');
  }

  nouvelle(modele?: LigneBareme): void {
    const demain = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    this.fiche = {
      date_effet: demain, motif: '', devise: modele?.devise ?? this.ref,
      type_mission: modele?.type_mission ?? 'locale', categorie: modele?.categorie ?? null, ville: modele?.ville,
    };
    if (this.onglet.code === 'taux-change') this.fiche.devise = modele?.devise ?? 'EUR';
    this.erreurs = null;
    this.ligneModal?.show();
  }

  enregistrer(): void {
    if (this.onglet.code === 'devise' || this.enCours) return;
    this.enCours = true;
    this.erreurs = null;
    this.service.ajouter(this.onglet.code, this.fiche).subscribe({
      next: () => { this.enCours = false; this.ligneModal?.hide(); this.toast.success('Nouvelle valeur enregistrée.'); this.charger(); },
      error: e => { this.enCours = false; this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e, 'Vérifiez la saisie.')); },
    });
  }

  supprimer(l: LigneBareme): void {
    if (this.onglet.code === 'devise' || !confirm('Supprimer cette valeur à venir ?')) return;
    this.service.supprimer(this.onglet.code, l.id!).subscribe({
      next: () => { this.toast.success('Valeur supprimée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  enregistrerDevise(): void {
    this.service.enregistrerParametres({ devise_reference: this.deviseSaisie }).subscribe({
      next: p => { this.parametres = { ...this.parametres!, ...p }; this.toast.success('Devise de référence enregistrée.'); },
      error: e => this.toast.error(messageErreur(e, (e?.champs?.devise_reference ?? []).join(' ') || 'Refusé.')),
    });
  }

  erreur(cle: string): string | null {
    const e = this.erreurs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }
}
