// src/app/pages/demandes/a-valider/a-valider.component.ts
//
// Validations en attente (les miennes et celles reçues par délégation) et
// historique de mes validations.

import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { DemandesService, Tache, TypeDemande, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-a-valider',
  templateUrl: './a-valider.component.html',
})
export class AValiderComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastrService);

  onglet: 'en_attente' | 'faite' = 'en_attente';
  readonly icone = iconeType;
  readonly teinte = teinteType;
  types: TypeDemande[] = [];
  typeDemande: number | null = null;
  taches: Tache[] = [];
  total = 0;
  page = 1;
  chargement = true;

  readonly decisions: Record<string, string> = { approuvee: 'Approuvée', rejetee: 'Rejetée', retournee: 'Retournée' };
  readonly classesDecision: Record<string, string> = { approuvee: 't-ve', rejetee: 't-ro', retournee: 't-or' };

  ngOnInit(): void {
    this.service.types(true).subscribe(t => this.types = t);
    this.charger();
  }

  filtrer(): void { this.page = 1; this.charger(); }

  changer(onglet: 'en_attente' | 'faite'): void { this.onglet = onglet; this.page = 1; this.charger(); }

  charger(): void {
    this.chargement = true;
    this.service.taches(this.onglet, this.page, this.typeDemande).subscribe({
      next: r => { this.taches = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  pageChangee(e: { page: number }): void { this.page = e.page; this.charger(); }

  ouvrir(t: Tache): void { this.router.navigate(['/demandes', t.demande.id]); }

  depuis(d: string | null): string {
    if (!d) return '—';
    const jours = Math.floor((Date.now() - new Date(d).getTime()) / 86400000);
    return jours <= 0 ? "aujourd'hui" : jours === 1 ? 'hier' : `${jours} jours`;
  }
}
