// src/app/core/services/baremes/baremes.service.ts
//
// API du lot 3 : barèmes datés (per diem, tarifs, forfait, taux de change),
// paramètres système, lieux (pays, villes, distances), calcul des missions.

import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { ERREURS_DETAILLEES } from 'src/app/core/helpers/error.interceptor';
import { environment } from 'src/environments/environment';

export type CodeBareme = 'per-diem' | 'kilometrique' | 'transport-ville' | 'forfait-hors-pays' | 'taux-change';

export interface LigneBareme {
  id?: number; date_effet: string; motif: string; modifie_par_nom?: string | null; modifie_le?: string;
  montant?: string; devise?: string; taux?: string; type_mission?: string; type_mission_libelle?: string;
  categorie?: number | null; categorie_libelle?: string; ville?: number; ville_libelle?: string;
  precedente?: { id: number; date_effet: string; valeur: string; devise: string } | null;
  en_vigueur?: boolean; supprimable?: boolean;
}

export interface ParametreSysteme {
  devise_reference: string; taille_max_piece_mo: number; modifiable_devise?: boolean;
  raison_sociale?: string; adresse?: string; ville?: string; pays?: string; logo?: string | null;
  telephone?: string; fax?: string; centre_impots?: string; regime_imposition?: string;
  formulaires?: Record<string, Record<string, string>>; jours_ouvres?: number[];
  canal_email?: boolean; canal_push?: boolean; email_configure?: boolean; push_configure?: boolean;
}
export interface JourFerie { id?: number; date: string; libelle: string; }
export interface Pays { id?: number; code_iso: string; libelle: string; devise_usuelle: string; actif: boolean; nb_villes?: number; }
export interface Ville { id?: number; libelle: string; pays: number; pays_libelle?: string; pays_code?: string; actif: boolean; }
export interface Distance { id?: number; ville_a: number; ville_b: number; ville_a_libelle?: string; ville_b_libelle?: string; km: number; }

export interface LigneRecap {
  rubrique: string; libelle: string; base: string | null; unite: string; tarif: string | null; devise: string;
  taux: string | null; montant: string; montant_ref: string | null; signalement: string;
}
export interface Calcul {
  lignes: LigneRecap[]; total_ref: string; devise_reference?: string; nombre_jours?: number | null;
  erreurs: string[]; signalements: string[]; date_baremes?: string; categorie?: string | null;
  recalcul?: { ancien_total_ref: string | null; date_baremes: string };
  mission?: any; champs?: Record<string, string>;
}

export const MOYENS_TRANSPORT = [
  { code: 'transport_commun', libelle: 'Transport en commun' }, { code: 'vehicule_personnel', libelle: 'Véhicule personnel' },
  { code: 'vehicule_service', libelle: 'Véhicule de service' }, { code: 'avion', libelle: 'Avion' }, { code: 'autre', libelle: 'Autre' },
];
export const RUBRIQUES_FRAIS: Record<string, string> = {
  visa: 'Frais de visa', aerien: 'Transport aérien', hebergement: 'Hébergement', autres: 'Autres frais',
};
export const FRAIS_PAR_TYPE: Record<string, string[]> = {
  locale: ['hebergement', 'autres'], hors_pays: ['visa', 'aerien', 'hebergement', 'autres'],
};

const detaille = () => ({ context: new HttpContext().set(ERREURS_DETAILLEES, true) });

@Injectable({ providedIn: 'root' })
export class BaremesService {
  private readonly api = `${environment.apiUrl}/api/api`;

  constructor(private http: HttpClient) {}

  private params(v: Record<string, any>): HttpParams {
    let p = new HttpParams();
    for (const [k, x] of Object.entries(v)) if (x !== undefined && x !== null && x !== '') p = p.set(k, String(x));
    return p;
  }

  // ── Barèmes ───────────────────────────────────────────────
  lignes(code: CodeBareme, filtres: Record<string, any> = {}): Observable<LigneBareme[]> {
    return this.http.get<LigneBareme[]>(`${this.api}/baremes/${code}/`, { params: this.params(filtres) });
  }
  ajouter(code: CodeBareme, l: Partial<LigneBareme>): Observable<LigneBareme> {
    return this.http.post<LigneBareme>(`${this.api}/baremes/${code}/`, l, detaille());
  }
  supprimer(code: CodeBareme, id: number) { return this.http.delete(`${this.api}/baremes/${code}/${id}/`); }

  parametres(): Observable<ParametreSysteme> { return this.http.get<ParametreSysteme>(`${this.api}/parametres-systeme/`); }
  enregistrerParametres(p: Partial<ParametreSysteme>): Observable<ParametreSysteme> {
    return this.http.patch<ParametreSysteme>(`${this.api}/parametres-systeme/`, p, detaille());
  }

  envoyerLogo(fichier: File): Observable<ParametreSysteme> {
    const f = new FormData();
    f.append('logo', fichier);
    return this.http.patch<ParametreSysteme>(`${this.api}/parametres-systeme/`, f, detaille());
  }

  joursFeries(annee?: number): Observable<JourFerie[]> {
    return this.http.get<JourFerie[]>(`${this.api}/jours-feries/`, { params: this.params({ annee }) });
  }
  ajouterJourFerie(j: JourFerie): Observable<JourFerie> { return this.http.post<JourFerie>(`${this.api}/jours-feries/`, j, detaille()); }
  supprimerJourFerie(id: number) { return this.http.delete(`${this.api}/jours-feries/${id}/`); }

  // ── Lieux ─────────────────────────────────────────────────
  pays(tous = false): Observable<Pays[]> { return this.http.get<Pays[]>(`${this.api}/pays/`, { params: this.params({ tous: tous ? 1 : '' }) }); }
  enregistrerPays(p: Pays): Observable<Pays> {
    return p.id ? this.http.patch<Pays>(`${this.api}/pays/${p.id}/`, p, detaille()) : this.http.post<Pays>(`${this.api}/pays/`, p, detaille());
  }
  villes(f: { pays?: number; pays_code?: string; exclure_pays_code?: string; tous?: number } = {}): Observable<Ville[]> {
    return this.http.get<Ville[]>(`${this.api}/villes/`, { params: this.params(f) });
  }
  enregistrerVille(v: Ville): Observable<Ville> {
    return v.id ? this.http.patch<Ville>(`${this.api}/villes/${v.id}/`, v, detaille()) : this.http.post<Ville>(`${this.api}/villes/`, v, detaille());
  }
  supprimerVille(id: number) { return this.http.delete(`${this.api}/villes/${id}/`); }
  distances(ville?: number): Observable<Distance[]> {
    return this.http.get<Distance[]>(`${this.api}/distances/`, { params: this.params({ ville }) });
  }
  enregistrerDistance(d: Distance): Observable<Distance> {
    return d.id ? this.http.patch<Distance>(`${this.api}/distances/${d.id}/`, d, detaille())
                : this.http.post<Distance>(`${this.api}/distances/`, d, detaille());
  }
  supprimerDistance(id: number) { return this.http.delete(`${this.api}/distances/${id}/`); }

  // ── Calcul des missions ───────────────────────────────────
  calculer(typeDemande: number, mission: any, demande?: number | null): Observable<Calcul> {
    return this.http.post<Calcul>(`${this.api}/missions/calculer/`, { type_demande: typeDemande, mission, demande: demande ?? null });
  }
}
