// src/app/pages/dashboards/accueil/accueil.component.ts
//
// Accueil : mes demandes par statut, validations en attente, accès rapides.
// Les tableaux de bord par profil viendront au lot 6.

import { Component, OnInit, inject } from '@angular/core';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { DemandesService } from 'src/app/core/services/demandes/demandes.service';
import { GESTIONNAIRES, aUnRole } from 'src/app/core/helpers/roles';

@Component({
  selector: 'app-accueil',
  templateUrl: './accueil.component.html',
})
export class AccueilComponent implements OnInit {
  private readonly tokenStorage = inject(TokenStorageService);
  private readonly service = inject(DemandesService);

  prenom = '';
  gestionnaire = false;
  aValider = 0;
  compteurs: Record<string, number> = {};
  charge = false;

  readonly tuiles = [
    { cle: 'brouillon', libelle: 'Brouillons', icone: 'ri-draft-line', teinte: 'p-gr' },
    { cle: 'en_validation', libelle: 'En validation', icone: 'ri-loader-2-line', teinte: 'p-bl' },
    { cle: 'a_corriger', libelle: 'À corriger', icone: 'ri-arrow-go-back-line', teinte: 'p-or' },
    { cle: 'approuvee', libelle: 'Approuvées', icone: 'ri-checkbox-circle-line', teinte: 'p-ve' },
    { cle: 'rejetee', libelle: 'Rejetées', icone: 'ri-close-circle-line', teinte: 'p-ro' },
  ];

  ngOnInit(): void {
    const user = this.tokenStorage.getUser();
    this.prenom = user?.prenom || user?.username || '';
    this.gestionnaire = aUnRole(user, GESTIONNAIRES);
    this.service.compteurs().subscribe({
      next: c => { this.compteurs = c.mes_demandes; this.aValider = c.a_valider; this.charge = true; },
      error: () => this.charge = true,
    });
  }
}
