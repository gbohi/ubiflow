// src/app/pages/parametres/accueil-parametres/accueil-parametres.component.ts
//
// Page d'accueil des paramètres (maquette « web-2-parametres ») : une carte par
// liste de paramètres, regroupées par thème, avec leur nombre d'éléments.
// Chaque carte n'est affichée qu'aux rôles autorisés par la route qu'elle ouvre
// (mêmes règles que ParametresRoutingModule).

import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpClient } from '@angular/common/http';
import { of } from 'rxjs';
import { catchError, map } from 'rxjs/operators';
import { environment } from 'src/environments/environment';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { ADMINS, GESTIONNAIRES, aUnRole } from 'src/app/core/helpers/roles';

export interface CarteParametre {
  titre: string;
  description: string;
  icone: string;
  lien: string;
  roles: string[];
  /** Liste de l'API dont on affiche le nombre d'éléments (sans le préfixe /api/api/) */
  compte?: string;
  /** Mots-clés supplémentaires pour la recherche */
  motsCles?: string;
}

export interface GroupeParametres {
  titre: string;
  icone: string;
  /** Couleur de la pastille des cartes : p-bl, p-ve, p-or, p-ro */
  teinte: string;
  cartes: CarteParametre[];
}

/** Thèmes et cartes ; les rôles reprennent exactement ceux des routes */
const ADMIN_WORKFLOW = ['super_admin', 'admin', 'admin_workflow'];
const FINANCES = ['super_admin', 'admin', 'admin_finances', 'comptable', 'controleur'];

export const GROUPES_PARAMETRES: GroupeParametres[] = [
  {
    titre: 'Demandes', icone: 'ri-file-list-3-line', teinte: 'p-or',
    cartes: [
      { titre: 'Types de demande', description: 'Formulaires et pièces exigées', icone: 'ri-file-settings-line',
        lien: '/parametres/types-demande', roles: ADMIN_WORKFLOW, motsCles: 'formulaire champ pièce' },
      { titre: 'Circuits de validation', description: 'Étapes, valideurs, conditions, versions', icone: 'ri-git-merge-line',
        lien: '/parametres/workflows', roles: ADMIN_WORKFLOW, motsCles: 'workflow circuit valideur étape' },
      { titre: 'Périmètres de consultation', description: 'Ce que voient la direction et les contrôleurs', icone: 'ri-focus-3-line',
        lien: '/parametres/perimetres', roles: ADMINS, motsCles: 'direction contrôleur périmètre département agence tableau de bord' },
      { titre: 'Calendrier', description: 'Jours ouvrés et jours fériés (délais, rappels)', icone: 'ri-calendar-2-line',
        lien: '/parametres/calendrier', roles: ADMINS, motsCles: 'férié délai rappel escalade jour ouvré' },
      { titre: "Journal d'activité", description: 'Traçabilité des opérations', icone: 'ri-history-line',
        lien: '/parametres/journal', roles: ['super_admin', 'admin', 'controleur'], motsCles: 'audit trace historique' },
    ],
  },
  {
    titre: 'Finances', icone: 'ri-scales-3-line', teinte: 'p-ve',
    cartes: [
      { titre: 'Barèmes', description: 'Per diem, tarifs de transport, taux de change', icone: 'ri-scales-3-line',
        lien: '/parametres/baremes', roles: FINANCES, motsCles: 'per diem tarif kilométrique forfait devise taux change' },
      { titre: 'Société', description: "Raison sociale, logo, signataire de l'ordre de mission", icone: 'ri-building-4-line',
        lien: '/parametres/societe', roles: ['super_admin', 'admin', 'admin_finances'], motsCles: 'logo adresse ordre mission note de frais formulaire' },
      { titre: 'Lieux et distances', description: 'Pays, villes, distances du référentiel', icone: 'ri-map-pin-line',
        lien: '/parametres/lieux', roles: FINANCES, compte: 'villes/', motsCles: 'ville pays distance km destination' },
    ],
  },
  {
    titre: 'Utilisateurs & accès', icone: 'ri-team-line', teinte: 'p-ve',
    cartes: [
      { titre: 'Utilisateurs', description: 'Comptes, affectations, rôles, mots de passe', icone: 'ri-user-3-line',
        lien: '/parametres/user', roles: ADMINS, compte: 'users/', motsCles: 'agent employé compte mot de passe' },
      { titre: 'Rôles', description: 'Super administrateur, administrateur, gestionnaire, employé', icone: 'ri-shield-user-line',
        lien: '/parametres/role', roles: ADMINS, compte: 'groups/', motsCles: 'droits accès groupe' },
      { titre: 'Statuts', description: 'Statuts des comptes et des affectations', icone: 'ri-checkbox-circle-line',
        lien: '/parametres/statut', roles: ADMINS, compte: 'statuts/' },
      { titre: 'Import Excel', description: 'Créer ou mettre à jour les collaborateurs depuis un fichier', icone: 'ri-file-excel-2-line',
        lien: '/parametres/import-collaborateurs', roles: ADMINS, motsCles: 'excel import fichier rh synchronisation' },
    ],
  },
  {
    titre: 'Organisation', icone: 'ri-organization-chart', teinte: 'p-bl',
    cartes: [
      { titre: 'Agences', description: "Sites de l'entreprise", icone: 'ri-map-pin-line',
        lien: '/parametres/agence', roles: GESTIONNAIRES, compte: 'agences/', motsCles: 'site siège' },
      { titre: 'Organigramme', description: 'Départements et responsables à une date', icone: 'ri-node-tree',
        lien: '/parametres/organigramme', roles: GESTIONNAIRES, motsCles: 'arbre hiérarchie responsable n+1' },
      { titre: 'Départements', description: 'Départements et leur rattachement (département parent)', icone: 'ri-organization-chart',
        lien: '/parametres/departement', roles: ADMINS, compte: 'services/', motsCles: 'service direction' },
      { titre: 'Responsabilités', description: 'DG, DAF, responsables de département… et leurs titulaires', icone: 'ri-shield-star-line',
        lien: '/parametres/responsabilite', roles: ADMINS, compte: 'responsabilites/', motsCles: 'valideur dg daf chef comptable responsable titulaire' },
      { titre: 'Postes', description: 'Postes occupés, par fonction et département', icone: 'ri-briefcase-4-line',
        lien: '/parametres/poste', roles: ADMINS, compte: 'postes/', motsCles: 'emploi métier' },
      { titre: 'Fonctions', description: 'Fonctions exercées par les agents', icone: 'ri-user-star-line',
        lien: '/parametres/fonction', roles: ADMINS, compte: 'fonctions/' },
      { titre: 'Catégories de salarié', description: 'Cadre, agent de maîtrise, employé…', icone: 'ri-price-tag-3-line',
        lien: '/parametres/categorie-salarie', roles: ADMINS, compte: 'categoriesalaries/', motsCles: 'cadre agent' },
    ],
  },
];

@Component({
  selector: 'app-accueil-parametres',
  templateUrl: './accueil-parametres.component.html',
})
export class AccueilParametresComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly tokenStorage = inject(TokenStorageService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly api = `${environment.apiUrl}/api/api/`;

  /** Thèmes réduits aux cartes accessibles à l'utilisateur */
  groupes: GroupeParametres[] = [];
  /** Nombre d'éléments par lien de carte (absent = en cours / indisponible) */
  comptes: Record<string, number> = {};
  recherche = '';

  ngOnInit(): void {
    const user = this.tokenStorage.getUser();
    this.groupes = GROUPES_PARAMETRES
      .map(g => ({ ...g, cartes: g.cartes.filter(c => aUnRole(user, c.roles)) }))
      .filter(g => g.cartes.length > 0);

    for (const carte of this.groupes.flatMap(g => g.cartes)) {
      if (!carte.compte) continue;
      const sep = carte.compte.includes('?') ? '&' : '?';
      this.http.get<any>(`${this.api}${carte.compte}${sep}page_size=1`).pipe(
        map(r => Array.isArray(r) ? r.length : Number(r?.count)),
        catchError(() => of(NaN)),
        takeUntilDestroyed(this.destroyRef),
      ).subscribe(n => { if (Number.isFinite(n)) this.comptes[carte.lien] = n; });
    }
  }

  get nbCartes(): number {
    return this.groupes.reduce((n, g) => n + g.cartes.length, 0);
  }

  /** Thèmes filtrés par la recherche (titre, description, mots-clés, thème) */
  get groupesFiltres(): GroupeParametres[] {
    const q = this.normaliser(this.recherche);
    if (!q) return this.groupes;
    return this.groupes
      .map(g => ({
        ...g,
        cartes: g.cartes.filter(c =>
          this.normaliser(`${g.titre} ${c.titre} ${c.description} ${c.motsCles ?? ''}`).includes(q)),
      }))
      .filter(g => g.cartes.length > 0);
  }

  private normaliser(s: string): string {
    return (s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').trim();
  }
}
