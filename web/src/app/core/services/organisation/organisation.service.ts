// src/app/core/services/organisation/organisation.service.ts
//
// API du lot « Organisation » : départements (arbre), responsabilités et
// titulaires, N+1 historisés, véhicule, situation d'un collaborateur, import Excel.

import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from 'src/environments/environment';

export interface Personne { id: number; matricule: string; nom: string; prenom: string; nom_complet: string; }

export interface Responsabilite {
  id?: number; code: string; libelle: string;
  portee: 'globale' | 'departement' | 'agence'; portee_libelle?: string;
  multiple: boolean; systeme?: boolean; actif: boolean; nb_titulaires?: number;
}

export interface AffectationResponsabilite {
  id?: number; user: number; user_nom?: string; user_matricule?: string;
  responsabilite: number; responsabilite_libelle?: string; portee?: string;
  departement?: number | null; departement_libelle?: string;
  agence?: number | null; agence_libelle?: string;
  date_debut: string; date_fin?: string | null; motif?: string;
}

export interface AffectationHierarchique {
  id?: number; user: number; mode: 'automatique' | 'designe'; mode_libelle?: string;
  responsable?: number | null; responsable_nom?: string; responsable_matricule?: string;
  date_debut: string; date_fin?: string | null; exceptionnelle?: boolean; motif?: string;
}

export interface SituationVehicule {
  id?: number; user: number; possede_vehicule: boolean; date_debut: string; date_fin?: string | null;
  commentaire?: string;
}

export interface ResolutionN1 {
  personne: Personne | null; source: 'designe' | 'departement' | 'departement_parent' | 'introuvable';
  message: string; departement: string | null; mode: string; exceptionnelle: boolean;
}

export interface OrganisationCollaborateur {
  date: string; collaborateur: Personne; statut: string | null;
  departement: { id: number; libelle: string } | null;
  agence: { id: number; libelle: string } | null;
  poste: { id: number; libelle: string; fonction: string | null } | null;
  categorie: { id: number; libelle: string } | null;
  possede_vehicule: boolean | null;
  n_plus_1: ResolutionN1; n_plus_2: ResolutionN1;
  responsabilites: { id: number; code: string; libelle: string; departement: string | null;
                     agence: string | null; date_debut: string; date_fin: string | null }[];
}

export interface NoeudDepartement {
  id: number; libelle: string; code: string; responsable: Personne | null; enfants: NoeudDepartement[];
}

export interface LigneRapportImport {
  ligne: number; matricule: string; resultat: 'cree' | 'mis_a_jour' | 'inchange' | 'rejete';
  messages: string[]; avertissement?: boolean;
}

export interface ImportCollaborateurs {
  id: number; fichier_nom: string; auteur_nom: string | null; cree_le: string; date_effet: string;
  simulation: boolean; nb_lignes: number; nb_crees: number; nb_mis_a_jour: number; nb_inchanges: number;
  nb_rejetes: number; rapport: LigneRapportImport[];
}

/** Liste paginée DRF, ou tableau simple */
const enTableau = <T>(r: any): T[] => Array.isArray(r) ? r : (r?.results ?? []);

@Injectable({ providedIn: 'root' })
export class OrganisationService {
  private readonly api = `${environment.apiUrl}/api/api`;

  constructor(private http: HttpClient) {}

  // ── Départements ──────────────────────────────────────────
  departementsTous(): Observable<any[]> {
    return this.http.get<any[]>(`${this.api}/allnopagin/services/`);
  }

  arbreDepartements(date?: string): Observable<NoeudDepartement[]> {
    return this.http.get<NoeudDepartement[]>(`${this.api}/departements/arbre/`, { params: this.params({ date }) });
  }

  agencesToutes(): Observable<any[]> {
    return this.http.get<any[]>(`${this.api}/allnopagin/agences/`);
  }

  categoriesToutes(): Observable<any[]> {
    return this.http.get<any[]>(`${this.api}/allnopagin/categoriesalaries/`);
  }

  collaborateursTous(): Observable<any[]> {
    return this.http.get<any[]>(`${this.api}/allnopagin/users/`);
  }

  // ── Responsabilités ───────────────────────────────────────
  responsabilites(search = ''): Observable<Responsabilite[]> {
    return this.http.get<any>(`${this.api}/responsabilites/`, { params: this.params({ search, page_size: 1000 }) })
      .pipe(map(r => enTableau<Responsabilite>(r)));
  }

  enregistrerResponsabilite(r: Responsabilite): Observable<Responsabilite> {
    return r.id ? this.http.patch<Responsabilite>(`${this.api}/responsabilites/${r.id}/`, r)
                : this.http.post<Responsabilite>(`${this.api}/responsabilites/`, r);
  }

  supprimerResponsabilite(id: number): Observable<unknown> {
    return this.http.delete(`${this.api}/responsabilites/${id}/`);
  }

  affectationsResponsabilite(filtres: { responsabilite?: number; user?: number; en_cours?: string }): Observable<AffectationResponsabilite[]> {
    return this.http.get<any>(`${this.api}/affectations-responsabilite/`, { params: this.params({ ...filtres, page_size: 1000 }) })
      .pipe(map(r => enTableau<AffectationResponsabilite>(r)));
  }

  enregistrerAffectationResponsabilite(a: AffectationResponsabilite): Observable<AffectationResponsabilite> {
    return a.id ? this.http.patch<AffectationResponsabilite>(`${this.api}/affectations-responsabilite/${a.id}/`, a)
                : this.http.post<AffectationResponsabilite>(`${this.api}/affectations-responsabilite/`, a);
  }

  supprimerAffectationResponsabilite(id: number): Observable<unknown> {
    return this.http.delete(`${this.api}/affectations-responsabilite/${id}/`);
  }

  // ── Hiérarchie ────────────────────────────────────────────
  affectationsHierarchiques(user: number): Observable<AffectationHierarchique[]> {
    return this.http.get<any>(`${this.api}/affectations-hierarchiques/`, { params: this.params({ user, page_size: 1000 }) })
      .pipe(map(r => enTableau<AffectationHierarchique>(r)));
  }

  enregistrerAffectationHierarchique(a: AffectationHierarchique): Observable<AffectationHierarchique> {
    return a.id ? this.http.patch<AffectationHierarchique>(`${this.api}/affectations-hierarchiques/${a.id}/`, a)
                : this.http.post<AffectationHierarchique>(`${this.api}/affectations-hierarchiques/`, a);
  }

  supprimerAffectationHierarchique(id: number): Observable<unknown> {
    return this.http.delete(`${this.api}/affectations-hierarchiques/${id}/`);
  }

  reaffecterN1(user: number, donnees: { mode: string; responsable: number | null; date_effet: string; motif: string }) {
    return this.http.post<{ affectation: AffectationHierarchique; n_plus_1: ResolutionN1 }>(
      `${this.api}/collaborateurs/${user}/reaffecter-n-plus-1/`, donnees);
  }

  // ── Véhicule ──────────────────────────────────────────────
  situationsVehicule(user: number): Observable<SituationVehicule[]> {
    return this.http.get<any>(`${this.api}/situations-vehicule/`, { params: this.params({ user, page_size: 1000 }) })
      .pipe(map(r => enTableau<SituationVehicule>(r)));
  }

  enregistrerSituationVehicule(s: SituationVehicule): Observable<SituationVehicule> {
    return s.id ? this.http.patch<SituationVehicule>(`${this.api}/situations-vehicule/${s.id}/`, s)
                : this.http.post<SituationVehicule>(`${this.api}/situations-vehicule/`, s);
  }

  supprimerSituationVehicule(id: number): Observable<unknown> {
    return this.http.delete(`${this.api}/situations-vehicule/${id}/`);
  }

  // ── Situation d'un collaborateur ──────────────────────────
  organisation(user: number | 'moi', date?: string): Observable<OrganisationCollaborateur> {
    return this.http.get<OrganisationCollaborateur>(`${this.api}/collaborateurs/${user}/organisation/`,
      { params: this.params({ date }) });
  }

  // ── Import Excel ──────────────────────────────────────────
  imports(): Observable<ImportCollaborateurs[]> {
    return this.http.get<any>(`${this.api}/imports-collaborateurs/`, { params: this.params({ page_size: 50 }) })
      .pipe(map(r => enTableau<ImportCollaborateurs>(r)));
  }

  importer(fichier: File, dateEffet: string, simulation: boolean): Observable<ImportCollaborateurs> {
    const donnees = new FormData();
    donnees.append('fichier', fichier);
    donnees.append('date_effet', dateEffet);
    donnees.append('simulation', simulation ? 'true' : 'false');
    return this.http.post<ImportCollaborateurs>(`${this.api}/imports-collaborateurs/`, donnees);
  }

  modeleImport(): Observable<Blob> {
    return this.http.get(`${this.api}/imports-collaborateurs/modele/`, { responseType: 'blob' });
  }

  private params(valeurs: Record<string, any>): HttpParams {
    let p = new HttpParams();
    for (const [cle, valeur] of Object.entries(valeurs)) {
      if (valeur !== undefined && valeur !== null && valeur !== '') p = p.set(cle, String(valeur));
    }
    return p;
  }
}

/** Date du jour au format AAAA-MM-JJ (heure locale) */
export function aujourdhui(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Message d'erreur lisible (l'intercepteur renvoie déjà une chaîne) */
export function messageErreur(err: any, defaut = 'Opération refusée.'): string {
  if (typeof err === 'string' && err) return err;
  if (err && typeof err.message === 'string' && err.message) return err.message;
  return defaut;
}
