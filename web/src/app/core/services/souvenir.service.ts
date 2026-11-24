// src/app/core/services/souvenir.service.ts
//
// « Se souvenir de moi » : mémorise sur ce navigateur le matricule (et le nom
// affiché dans la carte « Bon retour ») du dernier utilisateur qui l'a demandé.
// Le mot de passe n'est jamais enregistré. Indépendant de la session : la
// déconnexion n'efface pas ce souvenir ; « Changer » ou la case décochée, si.

import { Injectable } from '@angular/core';

export interface Souvenir { matricule: string; nom: string; }

const CLE = 'ubiflow.souvenir';

@Injectable({ providedIn: 'root' })
export class SouvenirService {
  lire(): Souvenir | null {
    try {
      const s = JSON.parse(localStorage.getItem(CLE) || 'null');
      return s && typeof s.matricule === 'string' && s.matricule ? { matricule: s.matricule, nom: String(s.nom || '') } : null;
    } catch {
      return null;
    }
  }

  enregistrer(matricule: string, nom: string): void {
    localStorage.setItem(CLE, JSON.stringify({ matricule, nom }));
  }

  oublier(): void { localStorage.removeItem(CLE); }
}

/** Initiales du nom affiché (« KONE Fatou » → « FK », prénom d'abord comme ailleurs) */
export function initialesSouvenir(nom: string, matricule: string): string {
  const mots = nom.trim().split(/\s+/).filter(Boolean);
  if (mots.length >= 2) return (mots[mots.length - 1][0] + mots[0][0]).toUpperCase();
  return (mots[0]?.[0] ?? matricule[0] ?? '?').toUpperCase();
}
