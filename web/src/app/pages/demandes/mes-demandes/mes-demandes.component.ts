// src/app/pages/demandes/mes-demandes/mes-demandes.component.ts
//
// Mes demandes (et, pour les profils de gestion, toutes les demandes) :
// filtres par statut, recherche, pagination serveur.

import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { CLASSES_STATUT, Demande, DemandesService, TypeDemande, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ToastrService } from 'ngx-toastr';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

const ROLES_GESTION = ['super_admin', 'admin', 'admin_workflow', 'direction', 'controleur', 'comptable'];

@Component({
  selector: 'app-mes-demandes',
  templateUrl: './mes-demandes.component.html',
})
export class MesDemandesComponent implements OnInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Référence', champ: d => d.reference || 'Brouillon' }, { libelle: 'Type', champ: 'type_libelle' },
    { libelle: 'Demandeur', champ: 'demandeur_nom' }, { libelle: 'Objet', champ: 'objet' },
    { libelle: 'Montant demandé', champ: 'montant_demande', format: 'montant', devise: 'devise' },
    { libelle: 'Montant approuvé', champ: 'montant_approuve', format: 'montant', devise: 'devise' },
    { libelle: 'Statut', champ: 'statut_libelle' }, { libelle: 'Paiement', champ: 'statut_financier_libelle' },
    { libelle: 'Étape en cours', champ: d => d.etape_en_cours ? `${d.etape_en_cours.libelle} (${d.etape_en_cours.valideurs.join(', ')})` : '' },
    { libelle: 'Date de la demande', champ: d => d.soumise_le || d.created_at, format: 'dateheure' },
  ];
  get paramsExport(): Record<string, any> { return { vue: this.vue, statut: this.statut, type_demande: this.typeDemande, famille: this.famille, du: this.du, au: this.au, search: this.recherche.trim() }; }

  private readonly service = inject(DemandesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);
  private readonly destroyRef = inject(DestroyRef);

  readonly classes = CLASSES_STATUT;
  readonly icone = iconeType;
  readonly teinte = teinteType;
  types: TypeDemande[] = [];
  typeDemande: number | null = null;
  /** Date de la demande (soumission, ou création pour un brouillon) */
  du = '';
  au = '';
  readonly filtres = [
    { cle: '', libelle: 'Toutes' }, { cle: 'brouillon', libelle: 'Brouillons' },
    { cle: 'en_validation', libelle: 'En validation' }, { cle: 'a_corriger', libelle: 'À corriger' },
    { cle: 'approuvee', libelle: 'Approuvées' }, { cle: 'rejetee', libelle: 'Rejetées' },
    { cle: 'annulee', libelle: 'Annulées' },
  ];
  readonly gestion = aUnRole(inject(TokenStorageService).getUser(), ROLES_GESTION);

  vue: 'mes' | 'toutes' = 'mes';
  statut = '';
  recherche = '';
  page = 1;
  total = 0;
  demandes: Demande[] = [];
  chargement = true;
  compteurs: Record<string, number> = {};
  /** Famille de types (« mission ») : lien « Tout voir » des prochaines missions */
  famille = '';
  private readonly recherche$ = new Subject<string>();

  ngOnInit(): void {
    const p = this.route.snapshot.queryParamMap;
    this.statut = p.get('statut') ?? '';
    this.vue = p.get('vue') === 'toutes' && this.gestion ? 'toutes' : 'mes';
    this.typeDemande = Number(p.get('type')) || null;
    this.famille = p.get('famille') ?? '';
    this.du = p.get('du') ?? '';
    this.au = p.get('au') ?? '';
    this.service.types(true).subscribe(t => this.types = t);
    this.recherche$.pipe(debounceTime(300), distinctUntilChanged(), takeUntilDestroyed(this.destroyRef))
      .subscribe(() => { this.page = 1; this.charger(); });
    this.charger();
    this.service.compteurs().subscribe(c => this.compteurs = c.mes_demandes);
  }

  charger(): void {
    this.chargement = true;
    this.service.demandes({ vue: this.vue, statut: this.statut, type_demande: this.typeDemande ?? '', famille: this.famille,
                            du: this.du, au: this.au, search: this.recherche.trim(), page: this.page })
      .subscribe({
        next: r => { this.demandes = r.results; this.total = r.count; this.chargement = false; },
        error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
      });
  }

  choisirStatut(cle: string): void {
    this.statut = cle;
    this.page = 1;
    this.router.navigate([], { queryParams: { statut: cle || null, vue: this.vue === 'toutes' ? 'toutes' : null,
                                              type: this.typeDemande || null, famille: this.famille || null, du: this.du || null, au: this.au || null } });
    this.charger();
  }

  /** Titre de la page : « Mes missions » quand la liste est limitée aux missions */
  get titre(): string {
    if (this.vue === 'toutes') return 'Toutes les demandes';
    return this.famille === 'mission' ? 'Mes missions' : 'Mes demandes';
  }

  changerVue(vue: 'mes' | 'toutes'): void {
    this.vue = vue;
    this.choisirStatut(this.statut);
  }

  rechercher(): void { this.recherche$.next(this.recherche); }

  effacerFiltres(): void {
    this.recherche = ''; this.typeDemande = null; this.du = ''; this.au = '';
    this.recherche$.next('');
    this.choisirStatut(this.statut);
  }

  pageChangee(e: { page: number }): void { this.page = e.page; this.charger(); }

  ouvrir(d: Demande): void { this.router.navigate(['/demandes', d.id]); }

  get totalCompteurs(): number { return Object.values(this.compteurs).reduce((a, b) => a + b, 0); }

  compte(cle: string): number | null {
    if (this.vue !== 'mes') return null;
    return cle ? (this.compteurs[cle] ?? 0) : this.totalCompteurs;
  }
}
