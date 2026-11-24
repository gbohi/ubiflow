// src/app/pages/demandes/recap-mission/recap-mission.component.ts
//
// Récapitulatif détaillé d'une mission (§7.6) : lignes, total en devise de
// référence, signalements à l'attention des valideurs et erreurs bloquantes.

import { Component, Input } from '@angular/core';
import { Calcul } from 'src/app/core/services/baremes/baremes.service';

@Component({
  selector: 'app-recap-mission',
  templateUrl: './recap-mission.component.html',
})
export class RecapMissionComponent {
  @Input() calcul: Calcul | null = null;
  /** Vrai : calcul en direct pendant la saisie (aperçu) ; faux : calcul figé à la soumission */
  @Input() apercu = false;
  @Input() chargement = false;

  readonly rubriques: Record<string, string> = {
    per_diem: 'Indemnités journalières', transport: 'Transport', visa: 'Frais de visa', aerien: 'Transport aérien',
    hebergement: 'Hébergement', autres: 'Autres frais',
  };

  get ref(): string { return this.calcul?.devise_reference || 'XOF'; }

  dateFr(iso?: string): string { return iso ? new Date(iso.slice(0, 10)).toLocaleDateString('fr-FR') : '—'; }
}
