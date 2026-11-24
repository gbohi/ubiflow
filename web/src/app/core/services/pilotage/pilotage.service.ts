// src/app/core/services/pilotage/pilotage.service.ts — tableaux de bord (lot 6)
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from 'src/environments/environment';

export interface Indicateur { cle: string; libelle: string; valeur: any; format: 'nombre' | 'montant' | 'heures' | 'jours'; aide: string; lien: string | null; ton: string; }
export interface Section {
  cle: string; titre: string; type: 'barres' | 'colonnes' | 'tableau'; unite?: string; aide?: string;
  donnees?: any[]; series?: { cle: string; libelle: string }[];
  colonnes?: { cle: string; libelle: string; format: string }[]; lignes?: any[];
}
export interface TableauDeBord {
  profil: string; titre: string; devise: string; du: string; au: string; genere_le: string;
  indicateurs: Indicateur[]; sections: Section[];
}
export interface Profil { code: string; libelle: string; icone: string; }

export interface ResultatRecherche {
  id: number; reference: string; objet: string; type: string; type_code: string; type_icone: string; statut: string;
  statut_libelle: string; demandeur: string; montant: string | null; devise: string;
}

@Injectable({ providedIn: 'root' })
export class PilotageService {
  private readonly api = `${environment.apiUrl}/api/api/tableaux-de-bord`;
  constructor(private http: HttpClient) {}

  /** Recherche globale de la barre du haut (demandes visibles par l'utilisateur) */
  rechercher(q: string): Observable<{ q: string; total: number; demandes: ResultatRecherche[] }> {
    return this.http.get<any>(`${environment.apiUrl}/api/api/recherche/`, { params: new HttpParams().set('q', q) });
  }

  accueil(profil?: string): Observable<any> {
    let p = new HttpParams();
    if (profil) p = p.set('profil', profil);
    return this.http.get<any>(`${environment.apiUrl}/api/api/accueil/`, { params: p });
  }
  profils(): Observable<Profil[]> { return this.http.get<Profil[]>(`${this.api}/`); }
  tableau(profil: string, filtres: Record<string, any>): Observable<TableauDeBord> {
    let p = new HttpParams();
    for (const [k, v] of Object.entries(filtres)) if (v !== null && v !== undefined && v !== '') p = p.set(k, String(v));
    return this.http.get<TableauDeBord>(`${this.api}/${profil}/`, { params: p });
  }
}
