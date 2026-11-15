// Paramètres › Suppléments (administrateurs) : familles de suppléments (Dessert ;
// plus tard Boisson, Entrée…). Un supplément accompagne le plat principal du
// jour : jamais seul, N par jour, inclus (gratuit pour l'employé, payé au
// prestataire à son tarif du type de plat) ou payant (tarif de la catégorie de
// salarié). Les types de plat sont reliés à une famille dans Types de plat.
// API : GET/POST supplements/familles/, PUT/DELETE supplements/familles/<id>/.
import { Component, OnInit, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ToastrService } from 'ngx-toastr';
import { environment } from 'src/environments/environment';

export interface FamilleSupplement {
  id?: number; libelle: string; inclus: boolean; max_par_jour: number; repas_offert: boolean; actif: boolean;
  ordre?: number; nb_types?: number; nb_plats?: number;
}

function erreur(e: any, defaut: string): string {
  const d = e?.error;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d[0] || defaut;
  return d?.detail || (d && typeof d === 'object' ? (Object.values(d).flat()[0] as string) : null) || defaut;
}

@Component({
  selector: 'app-supplements',
  templateUrl: './supplements.component.html',
})
export class SupplementsComponent implements OnInit {
  private http = inject(HttpClient);
  private toastr = inject(ToastrService);
  private api = `${environment.apiUrl}/api/api/supplements/familles/`;

  familles: FamilleSupplement[] = [];
  chargement = true;
  edition: FamilleSupplement | null = null;
  envoi = false;

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement = true;
    this.http.get<FamilleSupplement[]>(this.api).subscribe({
      next: f => { this.familles = f; this.chargement = false; },
      error: e => { this.chargement = false; this.toastr.error(erreur(e, 'Chargement impossible.')); },
    });
  }

  nouvelle(): void {
    this.edition = { libelle: '', inclus: true, max_par_jour: 1, repas_offert: true, actif: true };
  }

  modifier(f: FamilleSupplement): void { this.edition = { ...f }; }

  enregistrer(): void {
    const f = this.edition;
    if (!f || this.envoi) return;
    if (!f.libelle.trim()) { this.toastr.warning('Indiquez le nom de la famille (ex. Dessert).'); return; }
    this.envoi = true;
    const corps = { libelle: f.libelle.trim(), inclus: f.inclus, max_par_jour: Number(f.max_par_jour) || 1,
                    repas_offert: f.repas_offert, actif: f.actif };
    const req = f.id ? this.http.put(`${this.api}${f.id}/`, corps) : this.http.post(this.api, corps);
    req.subscribe({
      next: () => { this.envoi = false; this.edition = null; this.toastr.success('Famille enregistrée.'); this.charger(); },
      error: e => { this.envoi = false; this.toastr.error(erreur(e, 'Enregistrement impossible.')); },
    });
  }

  supprimer(f: FamilleSupplement): void {
    if (!f.id || !confirm(`Supprimer la famille « ${f.libelle} » ?`)) return;
    this.http.delete(`${this.api}${f.id}/`).subscribe({
      next: () => { this.toastr.success('Famille supprimée.'); this.charger(); },
      error: e => this.toastr.error(erreur(e, 'Suppression impossible.')),
    });
  }
}
