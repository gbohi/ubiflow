// src/app/account/auth-panneau/auth-panneau.component.ts
//
// Panneau de marque UbiFlow (bleu marine) des pages de connexion et de mot
// de passe oublié. Sur petit écran, il devient un bandeau en haut de page.

import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-auth-panneau',
  templateUrl: './auth-panneau.component.html',
})
export class AuthPanneauComponent {
  /** Titre court affiché sur petit écran (le panneau complet est masqué). */
  @Input() titreCourt = 'Vos demandes, suivies de bout en bout.';
  annee = new Date().getFullYear();
}
