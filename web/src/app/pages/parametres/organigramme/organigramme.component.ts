// src/app/pages/parametres/organigramme/organigramme.component.ts
//
// Arbre des départements avec leur responsable à une date donnée : permet de
// vérifier d'un coup d'œil d'où viendra le N+1 automatique de chacun.

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import {
  NoeudDepartement, OrganisationService, aujourdhui, messageErreur,
} from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-organigramme',
  templateUrl: './organigramme.component.html',
  styles: [`
    .org-arbre, .org-arbre ul { list-style: none; margin: 0; padding-left: 0; }
    .org-arbre ul { padding-left: 26px; border-left: 1px dashed var(--bs-border-color); margin-left: 14px; }
    .org-noeud { display: flex; align-items: center; gap: 10px; padding: 8px 10px; margin: 4px 0;
                 border: 1px solid var(--bs-border-color); border-radius: 10px; background: var(--bs-body-bg); }
    .org-noeud .org-ic { width: 30px; height: 30px; border-radius: 8px; display: grid; place-items: center;
                         background: rgba(15, 58, 110, .08); color: #0F3A6E; }
    .org-resp { margin-left: auto; font-size: .85rem; }
    .org-manque { color: var(--bs-danger); }
  `],
})
export class OrganigrammeComponent implements OnInit {
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);

  date = aujourdhui();
  arbre: NoeudDepartement[] = [];
  chargement = true;

  ngOnInit(): void { this.charger(); }

  charger(): void {
    this.chargement = true;
    this.organisation.arbreDepartements(this.date).subscribe({
      next: a => { this.arbre = a; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  get sansResponsable(): number {
    const compter = (n: NoeudDepartement[]): number =>
      n.reduce((t, x) => t + (x.responsable ? 0 : 1) + compter(x.enfants), 0);
    return compter(this.arbre);
  }
}
