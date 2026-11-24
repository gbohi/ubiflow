// src/app/account/telecharger/telecharger.component.ts
//
// Page publique « Application mobile » (liens Android et iPhone de la page de
// connexion). Les adresses des stores se renseignent ci-dessous une fois
// l'application publiée ; d'ici là, la page indique comment l'obtenir.

import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

/** Adresses Google Play et App Store (vides tant que l'application n'est pas publiée) */
export const LIENS_STORES = { android: '', ios: '' };

@Component({
  selector: 'app-telecharger',
  template: `
    <div class="auth-ub">
      <app-auth-panneau titreCourt="L'application UbiFlow sur votre téléphone."></app-auth-panneau>
      <main class="auth-ub-zone">
        <div class="auth-ub-carte">
          <h2 class="auth-ub-h2">Application mobile</h2>
          <p class="auth-ub-aide">Créez vos demandes, photographiez vos justificatifs et validez en déplacement, avec le même matricule et le même mot de passe.</p>
          @for (s of stores; track s.code) {
            <div class="auth-ub-store" [class.actif]="s.code === choisi">
              <i [class]="s.icone" aria-hidden="true"></i>
              <div>
                <b>{{ s.nom }}</b>
                <small>{{ s.lien ? s.disponible : 'Bientôt disponible sur ' + s.store }}</small>
              </div>
              @if (s.lien) { <a class="auth-ub-lien ms-auto" [href]="s.lien" target="_blank" rel="noopener">Installer</a> }
            </div>
          }
          @if (!stores[0].lien || !stores[1].lien) {
            <p class="auth-ub-aide mt-3 mb-0">En attendant la publication, le service informatique installe l'application sur votre téléphone professionnel.</p>
          }
          <a routerLink="/auth/login" class="auth-ub-bouton mt-4 text-decoration-none">Retour à la connexion</a>
        </div>
      </main>
    </div>`,
})
export class TelechargerComponent {
  readonly choisi = inject(ActivatedRoute).snapshot.queryParamMap.get('plateforme');
  readonly stores = [
    { code: 'android', nom: 'Android', store: 'Google Play', icone: 'ri-google-play-fill', lien: LIENS_STORES.android, disponible: 'Disponible sur Google Play' },
    { code: 'ios', nom: 'iPhone', store: "l'App Store", icone: 'ri-apple-fill', lien: LIENS_STORES.ios, disponible: "Disponible sur l'App Store" },
  ];
}
