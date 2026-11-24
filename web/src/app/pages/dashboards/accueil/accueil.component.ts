// src/app/pages/dashboards/accueil/accueil.component.ts
//
// Accueil de synthèse : comprendre en quelques secondes ce qui se passe et ce
// qu'il faut faire. Indicateurs, listes et graphiques selon le profil
// (collaborateur, valideur, direction, finances) ; actions rapides, alertes,
// notifications récentes, dernières activités et raccourcis pour tous.

import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { CLASSES_STATUT, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { PilotageService } from 'src/app/core/services/pilotage/pilotage.service';
import { complet } from '../graphes/format';

@Component({
  selector: 'app-accueil',
  templateUrl: './accueil.component.html',
  styles: [`
    .acc-kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 14px; }
    .acc-kpi { background: #fff; border: 1px solid var(--bs-border-color); border-radius: 14px; padding: 16px 18px; display: flex; gap: 14px;
               align-items: flex-start; color: inherit; text-decoration: none; transition: border-color .15s, box-shadow .15s; }
    a.acc-kpi:hover { border-color: #2a78d6; box-shadow: 0 4px 14px rgba(15, 58, 110, .08); }
    .acc-kpi .acc-ic { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; font-size: 20px;
                       background: #e8f0fd; color: #0F3A6E; flex-shrink: 0; }
    .acc-kpi.attention .acc-ic { background: #fef4e4; color: #9a6510; } .acc-kpi.alerte .acc-ic { background: #fde8e4; color: #c4381f; }
    .acc-kpi small { color: #52514e; display: block; font-size: 12.5px; }
    .acc-kpi b { font-size: 1.75rem; font-weight: 600; line-height: 1.15; display: block; }
    .acc-kpi .acc-u { font-size: 12px; font-weight: 500; color: #52514e; margin-left: 3px; }
    .acc-kpi .acc-st { font-size: 11.5px; color: #8a8984; }
    .acc-carte { background: #fff; border: 1px solid var(--bs-border-color); border-radius: 14px; padding: 16px 18px; }
    .acc-carte h6 { font-size: 14.5px; margin: 0; }
    .acc-actions { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
    .acc-action { border: 1px solid var(--bs-border-color); border-radius: 12px; padding: 14px 10px; text-align: center; color: inherit;
                  text-decoration: none; display: block; background: #fafbfd; transition: border-color .15s, background .15s; }
    .acc-action:hover { border-color: #2a78d6; background: #fff; }
    .acc-action i { font-size: 22px; color: #0F3A6E; display: block; margin-bottom: 4px; }
    .acc-action span { font-size: 13px; font-weight: 500; }
    .acc-ligne { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-top: 1px solid #f0efeb; color: inherit; text-decoration: none; }
    .acc-ligne:first-child { border-top: 0; }
    .acc-ligne:hover .acc-titre { color: #2a78d6; }
    .acc-titre { font-weight: 500; font-size: 13.5px; } .acc-sous { font-size: 12px; color: #8a8984; }
    .acc-alerte { border-radius: 10px; padding: 10px 14px; display: flex; align-items: center; gap: 10px; text-decoration: none; font-size: 13.5px; }
    .acc-alerte.attention { background: #fef4e4; color: #7a5009; } .acc-alerte.alerte { background: #fde8e4; color: #9e2c17; }
    .acc-notif { padding: 8px 0; border-top: 1px solid #f0efeb; font-size: 13px; } .acc-notif:first-child { border-top: 0; }
    .acc-notif.non-lue b::before { content: ''; display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #2a78d6; margin-right: 6px; }
  `],
})
export class AccueilComponent implements OnInit {
  private readonly service = inject(PilotageService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly classes = CLASSES_STATUT;
  readonly icone = iconeType;
  readonly teinte = teinteType;
  donnees: any = null;
  chargement = true;

  ngOnInit(): void { this.charger(this.route.snapshot.queryParamMap.get('profil') ?? undefined); }

  charger(profil?: string): void {
    this.chargement = true;
    this.service.accueil(profil).subscribe({
      next: d => { this.donnees = d; this.chargement = false; },
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

  depuis(iso: string | null): string {
    if (!iso) return '';
    const min = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
    if (min < 60) return min <= 1 ? "à l'instant" : `il y a ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `il y a ${h} h`;
    const j = Math.floor(h / 24);
    return j === 1 ? 'hier' : `il y a ${j} jours`;
  }
}
