// src/app/shared/export-liste/export-liste.component.ts
import { Component, Input, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ToastrService } from 'ngx-toastr';
import { firstValueFrom } from 'rxjs';
import { environment } from 'src/environments/environment';
import { Cellule, enregistrerPdf, exporterExcel, nomFichier, nouveauPdf, tableauPdf } from 'src/app/core/helpers/exports';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';

/** Colonne exportée : champ (chemin « a.b ») ou fonction, format facultatif */
export interface ColonneExport {
  libelle: string;
  champ: string | ((ligne: any) => Cellule);
  format?: 'date' | 'dateheure' | 'montant' | 'oui_non';
  /** Montant : chemin de la devise (ex. « devise ») ajoutée en PDF */
  devise?: string;
}

/**
 * Bouton « Exporter » (Excel, PDF) commun à toutes les listes. Les lignes sont
 * relues sur l'API avec les filtres en cours (toutes les pages), numérotées.
 *
 *   <app-export-liste titre="Agences" url="agences/" [params]="{ search: term }" [colonnes]="colonnesExport">
 *   </app-export-liste>
 *
 * `lignes` remplace l'appel à l'API (liste déjà complète en mémoire).
 */
@Component({
  selector: 'app-export-liste',
  template: `
    <div class="btn-group" dropdown placement="bottom right">
      <button type="button" class="btn-ubi" dropdownToggle [disabled]="enCours" aria-label="Exporter" data-test="exporter">
        @if (enCours) { <span class="spinner-border spinner-border-sm"></span> } @else { <i class="ri-download-2-line"></i> }
        <span class="pe-lib">Exporter</span>
      </button>
      <ul *dropdownMenu class="dropdown-menu dropdown-menu-end" role="menu">
        <li><button type="button" class="dropdown-item" (click)="exporter('xlsx')"><i class="ri-file-excel-2-line me-2 text-success"></i>Excel</button></li>
        <li><button type="button" class="dropdown-item" (click)="exporter('pdf')"><i class="ri-file-pdf-2-line me-2 text-danger"></i>PDF</button></li>
      </ul>
    </div>
  `,
})
export class ExportListeComponent {
  private readonly http = inject(HttpClient);
  private readonly toast = inject(ToastrService);
  private readonly tokens = inject(TokenStorageService);

  @Input({ required: true }) titre = '';
  /** Chemin de l'API sous /api/api/ (ex. « agences/ ») */
  @Input() url = '';
  @Input() params: Record<string, any> = {};
  @Input({ required: true }) colonnes: ColonneExport[] = [];
  @Input() lignes: any[] | null = null;
  /** Description des filtres (sous-titre du PDF) */
  @Input() filtres = '';

  enCours = false;

  private async charger(): Promise<any[]> {
    if (this.lignes) return this.lignes;
    let p = new HttpParams().set('page_size', 1000);
    for (const [k, v] of Object.entries(this.params ?? {})) {
      if (v !== null && v !== undefined && v !== '' && k !== 'page') p = p.set(k, String(v));
    }
    const toutes: any[] = [];
    for (let page = 1; page <= 50; page++) {
      const r: any = await firstValueFrom(this.http.get(`${environment.apiUrl}/api/api/${this.url}`, { params: p.set('page', page) }));
      if (Array.isArray(r)) return r;
      toutes.push(...(r?.results ?? []));
      if (!r?.next) break;
    }
    return toutes;
  }

  private valeur(ligne: any, c: ColonneExport, pdf: boolean): Cellule {
    const brute = typeof c.champ === 'function' ? c.champ(ligne)
      : c.champ.split('.').reduce((o: any, k) => (o === null || o === undefined ? o : o[k]), ligne);
    if (brute === null || brute === undefined || brute === '') return '';
    switch (c.format) {
      case 'date': return new Date(String(brute).length === 10 ? `${brute}T00:00:00` : brute).toLocaleDateString('fr-FR');
      case 'dateheure': return new Date(brute).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
      case 'oui_non': return brute ? 'Oui' : 'Non';
      case 'montant': {
        const n = Number(brute);
        if (Number.isNaN(n)) return String(brute);
        if (!pdf) return n;
        const devise = c.devise ? c.devise.split('.').reduce((o: any, k) => o?.[k], ligne) : '';
        return `${n.toLocaleString('fr-FR', { maximumFractionDigits: 2 }).replace(/[  ]/g, ' ')}${devise ? ' ' + devise : ''}`;
      }
      default: return typeof brute === 'object' ? JSON.stringify(brute) : brute;
    }
  }

  async exporter(format: 'xlsx' | 'pdf'): Promise<void> {
    if (this.enCours) return;
    this.enCours = true;
    try {
      const donnees = await this.charger();
      if (!donnees.length) { this.toast.info('Aucune ligne à exporter.'); return; }
      const fichier = nomFichier(this.titre, new Date().toISOString().slice(0, 10));
      const entete = ['N°', ...this.colonnes.map(c => c.libelle)];
      const corps = donnees.map((l, i) => [i + 1, ...this.colonnes.map(c => this.valeur(l, c, format === 'pdf'))]);
      // Excel : montants numériques (calculables) et devise dans une colonne à part
      const devise = this.colonnes.find(c => c.format === 'montant' && c.devise)?.devise;
      if (format === 'xlsx' && devise) {
        entete.push('Devise');
        corps.forEach((ligne, i) => ligne.push(devise.split('.').reduce((o: any, k) => o?.[k], donnees[i]) ?? ''));
      }
      if (format === 'xlsx') {
        exporterExcel(fichier, [{ nom: this.titre, lignes: [entete, ...corps] }]);
      } else {
        const u = this.tokens.getUser();
        const auteur = u ? `${u.prenom ?? ''} ${u.nom ?? ''}`.trim() || u.username : '';
        const sous = [`${donnees.length} ligne${donnees.length > 1 ? 's' : ''}`, this.filtres,
                      `édité le ${new Date().toLocaleString('fr-FR', { dateStyle: 'long', timeStyle: 'short' })}`,
                      auteur ? `par ${auteur}` : ''].filter(Boolean).join(' · ');
        const p = nouveauPdf(this.titre, sous, true);
        const droite = this.colonnes.map((c, i) => c.format === 'montant' ? i + 1 : -1).filter(i => i > 0);
        tableauPdf(p, entete, corps, false, [0, ...droite]);
        enregistrerPdf(p, fichier);
      }
    } catch (e: any) {
      this.toast.error(e?.message || "L'export a échoué.");
    } finally {
      this.enCours = false;
    }
  }
}
