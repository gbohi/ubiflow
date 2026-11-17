// Comptoir › Historique des retraits : retraits validés des jours précédents
// (période, recherche nom / matricule / plat, agence, « validé par », mode),
// pagination et export. Agent de comptoir : ses agences d'intervention.
import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime } from 'rxjs';
import { exporterExcel, nomFichier } from 'src/app/core/helpers/exports';
import {
  ContextePresta, EspacePrestataireService, HistoriqueRetraits, RetraitHistorique, couleur, initiales, isoJour,
  messageErreur, nombreFr,
} from 'src/app/core/services/espace-prestataire/espace-prestataire.service';

type Periode = 'jour' | 'mois' | 'precedent' | 'trimestre' | 'annee' | 'perso';

@Component({
  selector: 'app-historique-retraits',
  templateUrl: './historique-retraits.component.html',
})
export class HistoriqueRetraitsComponent implements OnInit {
  private api = inject(EspacePrestataireService);
  private destroyRef = inject(DestroyRef);
  private recherche$ = new Subject<void>();

  contexte: ContextePresta | null = null;
  periode: Periode = 'mois';
  debut = '';
  fin = '';
  agence: number | '' = '';
  validePar: number | 'moi' | '' = '';
  mode = '';
  recherche = '';
  page = 1;
  readonly parPage = 20;
  donnees: HistoriqueRetraits | null = null;
  chargement = true;
  erreur: string | null = null;
  exportEnCours = false;

  readonly initiales = initiales;
  readonly couleur = couleur;
  readonly nombreFr = nombreFr;
  readonly periodes: { cle: Periode; libelle: string }[] = [
    { cle: 'jour', libelle: "Aujourd'hui" },
    { cle: 'mois', libelle: 'Ce mois-ci' },
    { cle: 'precedent', libelle: 'Mois précédent' },
    { cle: 'trimestre', libelle: '3 derniers mois' },
    { cle: 'annee', libelle: 'Cette année' },
    { cle: 'perso', libelle: 'Personnalisée' },
  ];
  readonly modes = [
    { cle: '', libelle: 'Tous les modes' }, { cle: 'badge', libelle: "Badge d'accès" },
    { cle: 'scan', libelle: 'QR code' }, { cle: 'saisie', libelle: 'Matricule saisi' },
  ];

  ngOnInit(): void {
    this.api.contexte().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ next: c => this.contexte = c, error: () => {} });
    this.recherche$.pipe(debounceTime(350), takeUntilDestroyed(this.destroyRef)).subscribe(() => this.recharger());
    this.choisirPeriode('mois');
  }

  choisirPeriode(p: Periode): void {
    this.periode = p;
    const a = new Date();
    const y = a.getFullYear(), m = a.getMonth();
    const auj = isoJour(a);
    if (p === 'jour') { this.debut = auj; this.fin = auj; }
    if (p === 'mois') { this.debut = isoJour(new Date(y, m, 1)); this.fin = auj; }
    if (p === 'precedent') { this.debut = isoJour(new Date(y, m - 1, 1)); this.fin = isoJour(new Date(y, m, 0)); }
    if (p === 'trimestre') { this.debut = isoJour(new Date(y, m - 2, 1)); this.fin = auj; }
    if (p === 'annee') { this.debut = isoJour(new Date(y, 0, 1)); this.fin = auj; }
    if (p !== 'perso') this.recharger();
  }

  rechercher(): void { this.recherche$.next(); }

  recharger(): void { this.page = 1; this.charger(); }

  private get filtres() {
    return { debut: this.debut, fin: this.fin, agence: this.agence, valide_par: this.validePar, mode: this.mode,
             search: this.recherche.trim() };
  }

  charger(): void {
    if (!this.debut || !this.fin) return;
    this.chargement = true;
    this.api.historiqueRetraits({ ...this.filtres, page: this.page, page_size: this.parPage })
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
        next: d => { this.donnees = d; this.chargement = false; this.erreur = null; },
        error: e => { this.erreur = messageErreur(e, "L'historique n'a pas pu être chargé."); this.chargement = false; },
      });
  }

  changerPage(e: { page: number }): void { this.page = e.page; this.charger(); }

  get lignes(): RetraitHistorique[] { return this.donnees?.resultats ?? []; }

  platPrincipal(r: RetraitHistorique): string {
    return r.plats.filter(p => !p.supplement).map(p => p.plat).join(', ') || '—';
  }

  supplements(r: RetraitHistorique): string { return r.plats.filter(p => p.supplement).map(p => p.plat).join(', '); }

  libelleMode(m: string): string {
    return ({ badge: 'Badge', scan: 'QR code', saisie: 'Saisie' } as Record<string, string>)[m] || '—';
  }

  iconeMode(m: string): string {
    return ({ badge: 'ri-bank-card-2-line', scan: 'ri-qr-code-line', saisie: 'ri-keyboard-line' } as Record<string, string>)[m] || 'ri-question-line';
  }

  estMoi(r: RetraitHistorique): boolean { return !!this.contexte && r.valide_par_id === this.contexte.user.id; }

  exporter(): void {
    if (this.exportEnCours) return;
    this.exportEnCours = true;
    this.api.historiqueRetraits({ ...this.filtres, export: 1 }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: d => {
        this.exportEnCours = false;
        const lignes = [['Date', 'Heure', 'Employé', 'Matricule', 'Agence', 'Plat', 'Dessert', 'Mode', 'Validé par'],
          ...d.resultats.map(r => [r.date, r.heure, r.user_nom, r.matricule, r.agence, this.platPrincipal(r),
                                   this.supplements(r), this.libelleMode(r.mode), r.valide_par_nom || ''])];
        exporterExcel(nomFichier('historique-retraits', d.debut, d.fin) + '.xlsx', [{ nom: 'Retraits', lignes }]);
      },
      error: e => { this.exportEnCours = false; this.erreur = messageErreur(e, "L'export a échoué."); },
    });
  }
}
