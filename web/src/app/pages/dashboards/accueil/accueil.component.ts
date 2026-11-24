// src/app/pages/dashboards/accueil/accueil.component.ts
//
// Accueil de synthèse : comprendre en quelques secondes ce qui se passe et ce
// qu'il faut faire. Phrase de synthèse, barre d'actions unique, 4 indicateurs,
// bloc « À faire maintenant » (tout ce qui attend une action, les plus anciens
// d'abord), listes et graphiques de la vue, notifications et activité récente
// groupée par demande.

import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CLASSES_STATUT, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { PilotageService } from 'src/app/core/services/pilotage/pilotage.service';
import { complet } from '../graphes/format';

@Component({
  selector: 'app-accueil',
  templateUrl: './accueil.component.html',
  host: { class: 'acc-page' },
})
export class AccueilComponent implements OnInit {
  private readonly service = inject(PilotageService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly classes = CLASSES_STATUT;
  readonly icone = iconeType;
  readonly teinte = teinteType;
  donnees: any = null;
  /** Heure de référence des « il y a… » (fixée au chargement : affichage stable) */
  private maintenant = Date.now();
  chargement = true;

  ngOnInit(): void { this.charger(this.route.snapshot.queryParamMap.get('profil') ?? undefined); }

  charger(profil?: string): void {
    this.chargement = true;
    this.service.accueil(profil).subscribe({
      next: d => { this.maintenant = Date.now(); this.donnees = d; this.chargement = false; },
      error: () => this.chargement = false,
    });
  }

  choisir(code: string): void {
    this.router.navigate([], { queryParams: { profil: code }, replaceUrl: true });
    this.charger(code);
  }

  get dateDuJour(): string {
    const d = this.donnees?.aujourdhui ? new Date(this.donnees.aujourdhui + 'T00:00:00') : new Date();
    const t = d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  valeur(k: any): string { return complet(Number(k.valeur)); }

  lien(chemin: string | null): { route: string; params: any } | null {
    if (!chemin) return null;
    const [route, requete] = chemin.split('?');
    const params: any = {};
    for (const p of (requete ?? '').split('&').filter(Boolean)) { const [c, v] = p.split('='); params[c] = v; }
    return { route, params };
  }

  ouvrir(chemin: string | null): void {
    const l = this.lien(chemin);
    if (l) this.router.navigate([l.route], { queryParams: l.params });
  }

  montant(v: any): string { return `${complet(Number(v))} ${this.donnees?.devise ?? ''}`; }

  /** Nouvelle demande d'un type donné (ou choix du type) */
  nouvelle(code: string | null): void {
    this.router.navigate(['/demandes/nouvelle'], { queryParams: code ? { code } : {} });
  }

  libelleMotif(e: any): { texte: string; classe: string } | null {
    if (e.retard) return { texte: 'En retard', classe: 'm-retard' };
    return ({ a_payer: { texte: 'À payer', classe: 'm-payer' }, a_corriger: { texte: 'À corriger', classe: 'm-retard' },
              reversement: { texte: 'Reversement', classe: 'm-retard' } } as any)[e.motif] ?? null;
  }

  /** Action principale (pleine) pour payer et clôturer, secondaire pour le reste */
  actionPrincipale(e: any): boolean { return ['a_payer', 'a_cloturer', 'a_corriger'].includes(e.motif); }

  resumeActivite(a: any): string[] {
    return a.compte.map((c: any) => c.nombre > 1 ? `${c.type} ×${c.nombre}` : c.type);
  }

  depuis(iso: string | null): string {
    if (!iso) return '';
    const min = Math.floor((this.maintenant - new Date(iso).getTime()) / 60000);
    if (min < 60) return min <= 1 ? "à l'instant" : `il y a ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `il y a ${h} h`;
    const j = Math.floor(h / 24);
    return j === 1 ? 'hier' : `il y a ${j} jours`;
  }
}
