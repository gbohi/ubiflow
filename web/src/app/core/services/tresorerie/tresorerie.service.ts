// src/app/core/services/tresorerie/tresorerie.service.ts
//
// API du lot 4 : file à payer (et export Excel), règlements, reversements.

import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ERREURS_DETAILLEES } from 'src/app/core/helpers/error.interceptor';
import { environment } from 'src/environments/environment';
import { Demande } from '../demandes/demandes.service';

export interface Reglement {
  id: number; demande: number; montant: string; devise: string; taux_change: string; montant_ref: string;
  date_paiement: string; mode: string; mode_libelle: string; reference: string; beneficiaire: string;
  justificatif: number | null; justificatif_nom: string | null; enregistre_par_nom: string; enregistre_le: string;
  annule: boolean; annule_par_nom: string | null; annule_le: string | null; motif_annulation: string;
}

export interface Reversement {
  id: number; demande: number; demande_reference: string; demande_objet: string; demande_type: string;
  demandeur_nom: string; montant_du: string; devise: string; origine: string; origine_libelle: string; motif: string;
  etat: 'a_percevoir' | 'percu' | 'abandonne'; etat_libelle: string; cree_le: string; percu_le: string | null;
  mode: string; mode_libelle: string; reference: string; justificatif: number | null; justificatif_nom: string | null;
  motif_abandon: string; traite_par_nom: string | null; traite_le: string | null;
}

export const MODES_PAIEMENT = [
  { code: 'virement', libelle: 'Virement' }, { code: 'cheque', libelle: 'Chèque' }, { code: 'especes', libelle: 'Espèces' },
  { code: 'mobile_money', libelle: 'Mobile money' }, { code: 'autre', libelle: 'Autre' },
];

/** Rôles de la trésorerie (le backend applique les mêmes règles) */
export const ROLES_TRESORERIE = ['super_admin', 'admin', 'comptable', 'admin_finances'];
export const ROLES_ADMIN_FINANCES = ['super_admin', 'admin', 'admin_finances'];

const detaille = () => ({ context: new HttpContext().set(ERREURS_DETAILLEES, true) });

@Injectable({ providedIn: 'root' })
export class TresorerieService {
  private readonly api = `${environment.apiUrl}/api/api/tresorerie`;

  constructor(private http: HttpClient) {}

  private params(v: Record<string, any>): HttpParams {
    let p = new HttpParams();
    for (const [k, x] of Object.entries(v)) if (x !== undefined && x !== null && x !== '') p = p.set(k, String(x));
    return p;
  }

  aPayer(f: Record<string, any>) {
    return this.http.get<{ count: number; results: Demande[] }>(`${this.api}/a-payer/`, { params: this.params(f) });
  }
  exporterAPayer(f: Record<string, any>): Observable<Blob> {
    return this.http.get(`${this.api}/a-payer/`, { params: this.params({ ...f, export: 'xlsx', page: '' }), responseType: 'blob' });
  }

  payer(d: { demande: number; montant: any; date_paiement: string; mode: string; reference: string; beneficiaire: string },
        justificatif?: File | null): Observable<Reglement> {
    const f = new FormData();
    for (const [k, v] of Object.entries(d)) if (v !== null && v !== undefined && v !== '') f.append(k, String(v));
    if (justificatif) f.append('justificatif', justificatif);
    return this.http.post<Reglement>(`${this.api}/reglements/`, f, detaille());
  }
  annulerReglement(id: number, motif: string) {
    return this.http.post<Reglement>(`${this.api}/reglements/${id}/annuler/`, { motif }, detaille());
  }

  reversements(f: { etat?: string; search?: string; page?: number }) {
    return this.http.get<{ count: number; results: Reversement[] }>(`${this.api}/reversements/`, { params: this.params(f) });
  }
  percevoir(id: number, d: { percu_le: string; mode: string; reference: string }, justificatif?: File | null) {
    const f = new FormData();
    for (const [k, v] of Object.entries(d)) if (v) f.append(k, v);
    if (justificatif) f.append('justificatif', justificatif);
    return this.http.post<Reversement>(`${this.api}/reversements/${id}/percevoir/`, f, detaille());
  }
  abandonner(id: number, motif: string) {
    return this.http.post<Reversement>(`${this.api}/reversements/${id}/abandonner/`, { motif }, detaille());
  }
}
