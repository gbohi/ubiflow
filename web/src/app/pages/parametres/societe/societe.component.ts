// src/app/pages/parametres/societe/societe.component.ts
//
// Informations de la société reprises dans l'ordre de mission et la note de
// frais : raison sociale, adresse, ville de signature, pays, logo, signataire
// de l'ordre de mission et références qualité des formulaires.

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { BaremesService, ParametreSysteme } from 'src/app/core/services/baremes/baremes.service';
import { OrganisationService, messageErreur } from 'src/app/core/services/organisation/organisation.service';

const FORMULAIRES = [
  { cle: 'note_frais_hors_pays', libelle: 'Note de frais de mission hors pays' },
  { cle: 'note_frais_pays', libelle: 'Note de frais de mission dans le pays' },
];

@Component({
  selector: 'app-societe',
  templateUrl: './societe.component.html',
})
export class SocieteComponent implements OnInit {
  private readonly service = inject(BaremesService);
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);

  readonly formulairesQualite = FORMULAIRES;
  fiche: ParametreSysteme | null = null;
  responsabilites: any[] = [];
  logo: File | null = null;
  apercuLogo: string | null = null;
  enCours = false;

  ngOnInit(): void {
    this.organisation.responsabilites().subscribe(r => this.responsabilites = r.filter((x: any) => x.actif));
    this.service.parametres().subscribe(p => {
      const f = { ...(p.formulaires ?? {}) };
      for (const c of [...FORMULAIRES.map(x => x.cle), 'ordre_mission']) f[c] = { ...(f[c] ?? {}) };
      this.fiche = { ...p, formulaires: f };
      this.apercuLogo = p.logo ?? null;
    });
  }

  choisirLogo(e: Event): void {
    this.logo = (e.target as HTMLInputElement).files?.[0] ?? null;
    if (this.logo) {
      const lecteur = new FileReader();
      lecteur.onload = () => this.apercuLogo = String(lecteur.result);
      lecteur.readAsDataURL(this.logo);
    }
  }

  enregistrer(): void {
    if (!this.fiche || this.enCours) return;
    this.enCours = true;
    const { raison_sociale, adresse, ville, pays, formulaires } = this.fiche;
    this.service.enregistrerParametres({ raison_sociale, adresse, ville, pays, formulaires }).subscribe({
      next: () => {
        if (!this.logo) { this.fin(); return; }
        this.service.envoyerLogo(this.logo).subscribe({ next: () => this.fin(), error: e => this.echec(e) });
      },
      error: e => this.echec(e),
    });
  }

  private fin(): void { this.enCours = false; this.logo = null; this.toast.success('Informations de la société enregistrées.'); }
  private echec(e: any): void { this.enCours = false; this.toast.error(messageErreur(e)); }
}
