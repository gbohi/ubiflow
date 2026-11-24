// src/app/pages/parametres/perimetres/perimetres.component.ts
//
// Périmètres de consultation (§3.2) : limitent ce qu'un profil direction,
// contrôleur ou gestionnaire voit dans les listes et les tableaux de bord.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { environment } from 'src/environments/environment';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';
import { HttpContext } from '@angular/common/http';
import { ERREURS_DETAILLEES } from 'src/app/core/helpers/error.interceptor';

@Component({
  selector: 'app-perimetres',
  templateUrl: './perimetres.component.html',
})
export class PerimetresComponent implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);
  private readonly api = `${environment.apiUrl}/api/api/perimetres-consultation/`;

  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;
  lignes: any[] = [];
  collaborateurs: any[] = [];
  departements: any[] = [];
  agences: any[] = [];
  fiche: any = { user: null, type: 'departement', departement: null, agence: null };
  erreurs: any = null;
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Collaborateur', champ: 'user_nom' }, { libelle: 'Périmètre', champ: 'type_libelle' },
    { libelle: 'Département', champ: 'departement_libelle' }, { libelle: 'Agence', champ: 'agence_libelle' },
  ];

  ngOnInit(): void {
    this.charger();
    this.organisation.collaborateursTous().subscribe(u => this.collaborateurs = (u ?? []).filter((x: any) => x.is_active)
      .map((x: any) => ({ id: x.id, libelle: `${x.nom} ${x.prenom} (${x.username})` })));
    this.organisation.departementsTous().subscribe(d => this.departements = d ?? []);
    this.organisation.agencesToutes().subscribe(a => this.agences = a ?? []);
  }

  charger(): void { this.http.get<any[]>(this.api).subscribe(l => this.lignes = l); }

  nouveau(): void { this.fiche = { user: null, type: 'departement', departement: null, agence: null }; this.erreurs = null; this.ficheModal?.show(); }

  enregistrer(): void {
    this.http.post(this.api, this.fiche, { context: new HttpContext().set(ERREURS_DETAILLEES, true) }).subscribe({
      next: () => { this.ficheModal?.hide(); this.toast.success('Périmètre enregistré.'); this.charger(); },
      error: e => { this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e, 'Vérifiez la saisie.')); },
    });
  }

  supprimer(l: any): void {
    if (!confirm(`Retirer ce périmètre de ${l.user_nom} ?`)) return;
    this.http.delete(`${this.api}${l.id}/`).subscribe({ next: () => this.charger(), error: e => this.toast.error(messageErreur(e)) });
  }

  erreur(c: string): string | null { const e = this.erreurs?.[c]; return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null; }
}
