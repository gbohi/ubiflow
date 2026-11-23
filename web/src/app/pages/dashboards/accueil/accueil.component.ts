// src/app/pages/dashboards/accueil/accueil.component.ts
//
// Accueil de l'application : message de bienvenue et accès rapides.
// Les tableaux de bord métier viendront avec les modules de la plateforme.

import { Component, OnInit, inject } from '@angular/core';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { GESTIONNAIRES, LIBELLES_ROLES, aUnRole, rolesUtilisateur } from 'src/app/core/helpers/roles';

@Component({
  selector: 'app-accueil',
  template: `
    <div class="lst">
      <app-page-entete [titre]="'Bonjour ' + prenom" icone="ri-home-4-line"
                       sousTitre="Bienvenue sur UbiFlow"></app-page-entete>

      <div class="lst-carte p-4">
        @if (roles.length) {
          <p class="mb-3">Vos rôles : <b>{{ roles.join(', ') }}</b></p>
        }
        @if (gestionnaire) {
          <a class="btn btn-primary" routerLink="/parametres/accueil">
            <i class="ri-settings-3-line me-1"></i> Paramètres
          </a>
        } @else {
          <p class="text-muted mb-0">Les modules de la plateforme seront bientôt disponibles.</p>
        }
      </div>
    </div>
  `,
})
export class AccueilComponent implements OnInit {
  private readonly tokenStorage = inject(TokenStorageService);

  prenom = '';
  roles: string[] = [];
  gestionnaire = false;

  ngOnInit(): void {
    const user = this.tokenStorage.getUser();
    this.prenom = user?.prenom || user?.username || '';
    this.roles = rolesUtilisateur(user).map(r => LIBELLES_ROLES[r] ?? r);
    this.gestionnaire = aUnRole(user, GESTIONNAIRES);
  }
}
