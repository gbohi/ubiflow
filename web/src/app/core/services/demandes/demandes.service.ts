// src/app/core/services/demandes/demandes.service.ts
//
// API du lot 2 : types de demande, demandes, validations (tâches), délégations,
// circuits de validation (versions, étapes, simulation), notifications, journal.

import { Injectable } from '@angular/core';
import { HttpClient, HttpContext, HttpParams } from '@angular/common/http';
import { ERREURS_DETAILLEES } from 'src/app/core/helpers/error.interceptor';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import { environment } from 'src/environments/environment';

export interface ChampType {
  id?: number; type_demande: number; code: string; libelle: string;
  nature: 'texte' | 'texte_long' | 'entier' | 'montant' | 'date' | 'datetime' | 'liste' | 'booleen' | 'collaborateur';
  nature_libelle?: string; obligatoire: boolean; options: string[]; ordre: number; aide: string;
  sensible: boolean; utilisable_en_condition: boolean; actif: boolean;
}

export interface ExigencePiece {
  id?: number; type_demande: number; type_piece: number; type_piece_libelle?: string;
  moment: 'soumission' | 'etape' | 'paiement' | 'cloture'; moment_libelle?: string; etape_code: string; obligatoire: boolean;
}

export interface TypeDemande {
  id?: number; code: string; libelle: string; description: string; famille: string; actif: boolean; icone: string;
  ordre: number; prefixe_reference: string; avec_montant: boolean; paiement_fractionne_autorise: boolean;
  separation_approbation_paiement: boolean; mode_cloture: string; rapport_obligatoire: boolean;
  annulation_demandeur: string[]; champs?: ChampType[]; exigences?: ExigencePiece[];
  circuit_publie?: { id: number; numero: number } | null; parametres?: Record<string, any>;
}

export interface TypePiece { id: number; code: string; libelle: string; actif: boolean; }

export interface Document {
  id: number; type_piece: number | null; type_piece_libelle: string | null; nom_origine: string; taille: number;
  empreinte: string; ajoute_par: number; ajoute_par_nom: string; ajoute_le: string; retire: boolean;
  retire_par_nom: string | null; motif_retrait: string; version_numero: number | null;
}

export interface EtapeCircuit {
  id: number; ordre: number; libelle: string; etat: string; etat_libelle: string; motif_saut: string; reprise: boolean;
  mode: string; regle_parallele: string; raison: string; valideurs_prevus: string[];
  taches: { id: number; valideur: string; etat: string; decision: string; traitee_par: string | null;
            traitee_le: string | null; auto_validation: boolean }[];
}

export interface CycleCircuit {
  cycle: number; etat: string; etat_libelle: string; version_workflow: number; creee_le: string; etapes: EtapeCircuit[];
}

export interface MaTache {
  id: number; etape: string; actions_autorisees: string[]; champs_modifiables: string[];
  pour_compte_de: string | null; auto_validation: boolean;
}

export interface Demande {
  id: number; reference: string | null; type_demande: number; type_code: string; type_libelle: string;
  type_icone?: string; alertes?: { code: string; message: string; demande?: number; reference?: string }[]; demandeur: number; demandeur_nom: string; objet: string; montant_demande: string | null;
  montant_approuve: string | null; devise: string; statut: string; statut_libelle: string;
  statut_financier: string; statut_financier_libelle: string; soumise_le: string | null; approuvee_le: string | null;
  created_at: string; updated_at: string;
  etape_en_cours: { libelle: string; ordre: number; valideurs: string[] } | null;
  // Détail
  cree_par_nom?: string; donnees?: Record<string, any>; champs?: ChampType[]; pieces_exigees?: ExigencePiece[];
  devise_reference?: string; montant_paye?: string; solde?: string | null; n_plus_1_nom?: string | null;
  departement_libelle?: string | null; agence_libelle?: string | null; categorie_libelle?: string | null;
  version_numero?: number | null; version_workflow_numero?: number | null; documents?: Document[];
  commentaires?: { id: number; auteur_nom: string; texte: string; creee_le: string }[];
  circuit?: CycleCircuit[]; mes_taches?: MaTache[]; origine_copie?: number | null; origine_copie_reference?: string | null;
  motif_annulation?: string; annulee_le?: string | null;
  type_famille?: string; type_parametres?: Record<string, any>; mission?: any; calcul?: any;
  demande_parent?: number | null; demande_parent_reference?: string | null; demande_parent_type?: string | null;
  cloturee_le?: string | null; paiement_fractionne?: boolean; montant_reverse?: string;
  reglements?: any[]; reversements?: any[];
  rattachees?: { id: number; reference: string | null; type_libelle: string; type_code: string; objet: string; statut: string;
                 statut_libelle: string; montant_approuve: string | null; montant_demande: string | null; devise: string }[];
  synthese?: { engage_total: string; paye_total: string; solde_total: string; complements: any[] } | null;
  cloture?: Cloture | null; montant_retenu?: string | null;
  actions?: { modifier: boolean; soumettre: boolean; supprimer: boolean; annuler: boolean; dupliquer: boolean;
              ajouter_document: boolean; commenter: boolean; payer?: boolean; demander_annulation?: boolean;
              frais_complementaires?: boolean; annuler_admin?: boolean; corriger_montant?: boolean; reaffecter?: boolean };
}

export interface Cloture {
  etat: 'brouillon' | 'soumise' | 'retournee' | 'validee'; etat_libelle: string; depart_reel: string | null; retour_reel: string | null;
  depenses: Record<string, string>; observations: string; soumise_le: string | null; controlee_le: string | null;
  controlee_par: string | null; motif_retour: string; controle: string | null; calcul: Record<string, any>;
  pieces_cloture: { id: number; libelle: string; obligatoire: boolean; fournie: boolean }[];
  actions: { modifier: boolean; controler: boolean };
}

export interface EntreePlan {
  etape: number; ordre: number; code: string; libelle: string; statut: 'prevue' | 'sautee' | 'bloquante';
  raison: string; mode: string; regle_parallele: string; quorum: number | null;
  valideurs: { id: number; nom: string; matricule: string; auto_validation: boolean; approbation_automatique: boolean }[];
}

export interface Action {
  id: number; type: string; type_libelle: string; auteur_nom: string; pour_compte_de_nom: string | null;
  etape_libelle: string | null; cycle: number | null; motif: string; donnees: any; auto_validation: boolean;
  canal: string; horodatage: string;
}

export interface Tache {
  id: number; etat: string; decision: string; etape: string; actions_autorisees: string[]; champs_modifiables: string[];
  valideur_nom: string; pour_compte_de: string | null; auto_validation: boolean; ouverte_le: string; traitee_le: string | null;
  demande: { id: number; reference: string; objet: string; type_libelle: string; type_code: string; type_icone?: string; demandeur: string;
             montant_demande: string | null; devise: string; statut: string; soumise_le: string };
}

export interface Delegation {
  id?: number; delegant?: number; delegant_nom?: string; delegataire: number; delegataire_nom?: string;
  date_debut: string; date_fin: string; motif: string; types_demande: number[]; responsabilites: number[];
  types_demande_libelles?: string[]; responsabilites_libelles?: string[]; etat?: string; revoquee?: boolean;
}

export interface RegleDesignation {
  id?: number; ordre?: number; mode: 'responsabilite' | 'personne' | 'relation'; responsabilite: number | null;
  responsabilite_libelle?: string; perimetre: string; personne: number | null; personne_nom?: string; relation: string;
}

export interface Etape {
  id?: number; version: number; ordre?: number; code: string; libelle: string; active: boolean; condition: any;
  mode: string; regle_parallele: string; quorum: number | null; actions_autorisees: string[]; champs_modifiables: string[];
  auto_validation_demandeur: string; meme_valideur_deja_passe: string; valideur_introuvable: string;
  valideur_secours: number | null; regles: RegleDesignation[]; description_condition?: string;
}

export interface VersionWorkflow {
  id: number; type_demande: number; type_code: string; type_libelle: string; numero: number; etat: string;
  etat_libelle: string; commentaire_version: string; reprise_apres_correction: string; publiee_le: string | null;
  publiee_par_nom: string | null; nb_demandes: number; etapes: Etape[];
}

export interface ChampCondition { code: string; libelle: string; nature: string; options?: string[]; }

export interface Notification {
  id: number; evenement: string; titre: string; message: string; lien: string; demande: number | null;
  demande_reference: string | null; lue: boolean; creee_le: string;
}

/** Teinte de la pastille d'un type de demande (listes, cartes) */
const TEINTES_TYPE: Record<string, string> = { MLO: 'p-ve', MHP: 'p-bl', FRC: 'p-or', PAI: 'p-ro', RMB: 'p-ve', FCM: 'p-bl' };
export function teinteType(code?: string | null): string { return TEINTES_TYPE[code ?? ''] ?? ''; }
export function iconeType(icone?: string | null): string { return icone || 'ri-file-text-line'; }

const detaille = () => ({ context: new HttpContext().set(ERREURS_DETAILLEES, true) });

const tableau = <T>(r: any): T[] => Array.isArray(r) ? r : (r?.results ?? []);

@Injectable({ providedIn: 'root' })
export class DemandesService {
  private readonly api = `${environment.apiUrl}/api/api`;

  constructor(private http: HttpClient) {}

  private params(v: Record<string, any>): HttpParams {
    let p = new HttpParams();
    for (const [k, x] of Object.entries(v)) if (x !== undefined && x !== null && x !== '') p = p.set(k, String(x));
    return p;
  }

  // ── Types de demande ──────────────────────────────────────
  types(tous = false): Observable<TypeDemande[]> {
    return this.http.get<TypeDemande[]>(`${this.api}/types-demande/`, { params: this.params({ tous: tous ? 1 : '' }) });
  }
  enregistrerType(t: Partial<TypeDemande>): Observable<TypeDemande> {
    const { champs, exigences, circuit_publie, ...donnees } = t as any;
    return t.id ? this.http.patch<TypeDemande>(`${this.api}/types-demande/${t.id}/`, donnees)
                : this.http.post<TypeDemande>(`${this.api}/types-demande/`, donnees);
  }
  enregistrerChamp(c: Partial<ChampType>): Observable<ChampType> {
    return c.id ? this.http.patch<ChampType>(`${this.api}/champs-type/${c.id}/`, c)
                : this.http.post<ChampType>(`${this.api}/champs-type/`, c);
  }
  supprimerChamp(id: number) { return this.http.delete(`${this.api}/champs-type/${id}/`); }
  enregistrerExigence(e: Partial<ExigencePiece>): Observable<ExigencePiece> {
    return e.id ? this.http.patch<ExigencePiece>(`${this.api}/exigences-pieces/${e.id}/`, e)
                : this.http.post<ExigencePiece>(`${this.api}/exigences-pieces/`, e);
  }
  supprimerExigence(id: number) { return this.http.delete(`${this.api}/exigences-pieces/${id}/`); }
  typesPieces(): Observable<TypePiece[]> { return this.http.get<TypePiece[]>(`${this.api}/types-pieces/`); }

  // ── Demandes ──────────────────────────────────────────────
  demandes(f: { vue?: string; statut?: string; type_demande?: number | string; du?: string; au?: string; search?: string; page?: number }) {
    return this.http.get<{ count: number; results: Demande[] }>(`${this.api}/demandes/`, { params: this.params(f) });
  }
  demande(id: number): Observable<Demande> { return this.http.get<Demande>(`${this.api}/demandes/${id}/`); }
  creer(d: { type_demande: number; objet: string; montant_demande: any; devise?: string; donnees: any; mission?: any;
          demande_parent?: number | null }) {
    return this.http.post<Demande>(`${this.api}/demandes/`, d, detaille());
  }
  modifier(id: number, d: { objet?: string; montant_demande?: any; donnees?: any; mission?: any }) {
    return this.http.patch<Demande>(`${this.api}/demandes/${id}/`, d, detaille());
  }
  supprimer(id: number) { return this.http.delete(`${this.api}/demandes/${id}/`); }
  soumettre(id: number, motif = '') { return this.http.post<Demande>(`${this.api}/demandes/${id}/soumettre/`, { motif }, detaille()); }
  annuler(id: number, motif: string) { return this.http.post<Demande>(`${this.api}/demandes/${id}/annuler/`, { motif }); }
  dupliquer(id: number) { return this.http.post<Demande>(`${this.api}/demandes/${id}/dupliquer/`, {}); }
  historique(id: number) { return this.http.get<Action[]>(`${this.api}/demandes/${id}/historique/`); }
  versions(id: number) { return this.http.get<any[]>(`${this.api}/demandes/${id}/versions/`); }
  commenter(id: number, texte: string) { return this.http.post(`${this.api}/demandes/${id}/commentaires/`, { texte }); }
  ajouterDocument(id: number, fichier: File, typePiece: number | null, remplace?: number) {
    const f = new FormData();
    f.append('fichier', fichier);
    if (typePiece) f.append('type_piece', String(typePiece));
    if (remplace) f.append('remplace', String(remplace));
    return this.http.post<Document>(`${this.api}/demandes/${id}/documents/`, f);
  }
  retirerDocument(id: number, doc: number, motif: string) {
    return this.http.post(`${this.api}/demandes/${id}/documents/${doc}/retirer/`, { motif });
  }
  telechargerDocument(id: number, doc: number): Observable<Blob> {
    return this.http.get(`${this.api}/demandes/${id}/documents/${doc}/fichier/`, { responseType: 'blob' });
  }
  parentsPossibles(typeDemande: number) {
    return this.http.get<any[]>(`${this.api}/demandes/parents-possibles/`, { params: this.params({ type_demande: typeDemande }) });
  }
  pdf(id: number, document: 'pdf' | 'ordre-mission' | 'note-frais' = 'pdf'): Observable<Blob> {
    return this.http.get(`${this.api}/demandes/${id}/${document}/`, { responseType: 'blob' });
  }
  enregistrerCloture(id: number, d: Partial<Cloture>) {
    return this.http.patch<Cloture>(`${this.api}/demandes/${id}/cloture/`, d, detaille());
  }
  actionCloture(id: number, quoi: 'soumettre' | 'valider' | 'retourner', motif = '') {
    return this.http.post<Demande>(`${this.api}/demandes/${id}/cloture/${quoi}/`, { motif }, detaille());
  }
  cloturesAControler() { return this.http.get<any[]>(`${this.api}/missions/clotures/`); }
  compteurs() {
    return this.http.get<{ mes_demandes: Record<string, number>; a_valider: number }>(`${this.api}/demandes/compteurs/`);
  }

  // ── Validations ───────────────────────────────────────────
  taches(etat = 'en_attente', page = 1, f: { type_demande?: number | null; du?: string; au?: string } = {}) {
    return this.http.get<{ count: number; results: Tache[] }>(`${this.api}/taches/`, { params: this.params({ etat, page, ...f }) });
  }
  agir(tache: number, action: 'approuver' | 'rejeter' | 'retourner', motif: string, modifications?: any) {
    return this.http.post<{ demande: number; statut: string; statut_libelle: string }>(
      `${this.api}/taches/${tache}/${action}/`, { motif, modifications });
  }
  reaffecter(tache: number, valideur: number, motif: string) {
    return this.http.post(`${this.api}/taches/${tache}/reaffecter/`, { valideur, motif }, detaille());
  }
  annulerAdmin(id: number, motif: string) { return this.http.post<Demande>(`${this.api}/demandes/${id}/annuler-admin/`, { motif }, detaille()); }
  corrigerMontant(id: number, montant: any, motif: string) {
    return this.http.post<Demande>(`${this.api}/demandes/${id}/corriger-montant/`, { montant, motif }, detaille());
  }

  // ── Délégations ───────────────────────────────────────────
  delegations(sens = '') { return this.http.get<Delegation[]>(`${this.api}/delegations/`, { params: this.params({ sens }) }); }
  creerDelegation(d: Delegation) { return this.http.post<Delegation>(`${this.api}/delegations/`, d); }
  revoquerDelegation(id: number) { return this.http.post<Delegation>(`${this.api}/delegations/${id}/revoquer/`, {}); }

  // ── Circuits ──────────────────────────────────────────────
  versionsWorkflow(typeDemande?: number) {
    return this.http.get<VersionWorkflow[]>(`${this.api}/versions-workflow/`, { params: this.params({ type_demande: typeDemande }) });
  }
  versionWorkflow(id: number) { return this.http.get<VersionWorkflow>(`${this.api}/versions-workflow/${id}/`); }
  nouvelleVersion(typeDemande: number, source?: number) {
    return this.http.post<VersionWorkflow>(`${this.api}/versions-workflow/`, { type_demande: typeDemande, source });
  }
  modifierVersion(id: number, d: Partial<VersionWorkflow>) {
    return this.http.patch<VersionWorkflow>(`${this.api}/versions-workflow/${id}/`, d);
  }
  supprimerVersion(id: number) { return this.http.delete(`${this.api}/versions-workflow/${id}/`); }
  controler(id: number) { return this.http.get<{ erreurs: string[] }>(`${this.api}/versions-workflow/${id}/controle/`); }
  publier(id: number, commentaire: string) {
    return this.http.post<VersionWorkflow>(`${this.api}/versions-workflow/${id}/publier/`, { commentaire }, detaille());
  }
  simuler(id: number, demandeur: number, montant: any, donnees: any) {
    return this.http.post<{ demandeur: any; n_plus_1: any; departement: string | null; plan: EntreePlan[] }>(
      `${this.api}/versions-workflow/${id}/simuler/`, { demandeur, montant, donnees });
  }
  reordonner(id: number, etapes: number[]) {
    return this.http.post<VersionWorkflow>(`${this.api}/versions-workflow/${id}/reordonner/`, { etapes });
  }
  enregistrerEtape(e: Partial<Etape>) {
    const { description_condition, ...donnees } = e as any;
    return e.id ? this.http.patch<Etape>(`${this.api}/etapes-workflow/${e.id}/`, donnees)
                : this.http.post<Etape>(`${this.api}/etapes-workflow/`, donnees);
  }
  supprimerEtape(id: number) { return this.http.delete(`${this.api}/etapes-workflow/${id}/`); }
  champsCondition(typeDemande: number) {
    return this.http.get<{ champs: ChampCondition[]; operateurs: { code: string; libelle: string }[] }>(
      `${this.api}/champs-condition/`, { params: this.params({ type_demande: typeDemande }) });
  }

  // ── Notifications, journal ────────────────────────────────
  notifications(nonLues = false) {
    return this.http.get<any>(`${this.api}/notifications/`, { params: this.params({ non_lues: nonLues ? 1 : '' }) })
      .pipe(map(r => tableau<Notification>(r)));
  }
  compteurNotifications() { return this.http.get<{ non_lues: number }>(`${this.api}/notifications/compteur/`); }
  lireNotification(id: number) { return this.http.post(`${this.api}/notifications/${id}/lire/`, {}); }
  toutLire() { return this.http.post(`${this.api}/notifications/tout-lire/`, {}); }
  journal(f: Record<string, any>) {
    return this.http.get<{ count: number; results: any[] }>(`${this.api}/journal/`, { params: this.params(f) });
  }
}

/** Classe de pastille selon le statut d'une demande */
export const CLASSES_STATUT: Record<string, string> = {
  brouillon: 't-gr', en_validation: 't-bl', a_corriger: 't-or', rejetee: 't-ro', approuvee: 't-ve',
  en_attente_cloture: 't-or', cloturee: 't-na', annulee: 't-gr',
};

/** Montant lisible : « 1 250 000 XOF » */
export function formaterMontant(m: string | number | null | undefined, devise = ''): string {
  if (m === null || m === undefined || m === '') return '—';
  const n = Number(m);
  const texte = n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 2 }).replace(/ /g, ' ');
  return devise ? `${texte} ${devise}` : texte;
}

/** Téléchargement d'un Blob sous un nom donné */
export function enregistrerFichier(blob: Blob, nom: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = nom;
  a.click();
  URL.revokeObjectURL(url);
}
