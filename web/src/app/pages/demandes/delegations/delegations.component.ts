// src/app/pages/demandes/delegations/delegations.component.ts
//
// Délégations de validations : celles que je donne, celles que je reçois ;
// création (pour moi, ou pour autrui par un administrateur des workflows) et révocation.

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { Delegation, DemandesService, TypeDemande } from 'src/app/core/services/demandes/demandes.service';
import { OrganisationService, Responsabilite, aujourdhui, messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-delegations',
  templateUrl: './delegations.component.html',
})
export class DelegationsComponent implements OnInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Délégant', champ: 'delegant_nom' }, { libelle: 'Délégataire', champ: 'delegataire_nom' },
    { libelle: 'Début', champ: 'date_debut', format: 'date' }, { libelle: 'Fin', champ: 'date_fin', format: 'date' },
    { libelle: 'Types de demande', champ: d => d.types_demande_libelles?.length ? d.types_demande_libelles.join(', ') : 'Tous les types' },
    { libelle: 'Validations', champ: d => d.responsabilites_libelles?.length ? d.responsabilites_libelles.join(', ') : 'Toutes' },
    { libelle: 'Motif', champ: 'motif' }, { libelle: 'État', champ: d => this.etats[d.etat || 'active']?.libelle ?? d.etat },
  ];

  private readonly service = inject(DemandesService);
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);
  readonly user = inject(TokenStorageService).getUser();
  readonly adminWorkflow = aUnRole(this.user, ['super_admin', 'admin', 'admin_workflow']);

  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;

  sens: '' | 'toutes' = '';
  delegations: Delegation[] = [];
  collaborateurs: { id: number; libelle: string }[] = [];
  types: TypeDemande[] = [];
  responsabilites: Responsabilite[] = [];
  fiche: Delegation = this.vide();
  pourAutrui = false;
  enCours = false;

  readonly etats: Record<string, { libelle: string; classe: string }> = {
    active: { libelle: 'Active', classe: 't-ve' }, planifiee: { libelle: 'Planifiée', classe: 't-bl' },
    terminee: { libelle: 'Terminée', classe: 't-gr' }, revoquee: { libelle: 'Révoquée', classe: 't-ro' },
  };

  ngOnInit(): void {
    this.charger();
    this.organisation.collaborateursTous().subscribe(u => this.collaborateurs = (u ?? []).filter(x => x.is_active)
      .map(x => ({ id: x.id, libelle: `${x.nom} ${x.prenom} (${x.username})` })));
    this.service.types().subscribe(t => this.types = t);
    this.organisation.responsabilites().subscribe(r => this.responsabilites = r.filter(x => x.actif));
  }

  private vide(): Delegation {
    return { delegataire: null as any, date_debut: aujourdhui(), date_fin: aujourdhui(), motif: '', types_demande: [], responsabilites: [] };
  }

  charger(): void {
    this.service.delegations(this.sens).subscribe({ next: d => this.delegations = d, error: e => this.toast.error(messageErreur(e)) });
  }

  donnee(d: Delegation): boolean { return d.delegant === this.user?.id; }

  nouvelle(): void { this.fiche = this.vide(); this.pourAutrui = false; this.ficheModal?.show(); }

  enregistrer(): void {
    const f = this.fiche;
    if (!f.delegataire || !f.date_debut || !f.date_fin) { this.toast.warning('Délégataire et période obligatoires.'); return; }
    if (this.pourAutrui && (!f.delegant || !f.motif.trim())) { this.toast.warning('Délégant et motif obligatoires.'); return; }
    const donnees: Delegation = { ...f, delegant: this.pourAutrui ? f.delegant : undefined };
    this.enCours = true;
    this.service.creerDelegation(donnees).subscribe({
      next: () => { this.enCours = false; this.ficheModal?.hide(); this.toast.success('Délégation enregistrée.'); this.charger(); },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e)); },
    });
  }

  revoquer(d: Delegation): void {
    if (!d.id || !confirm(`Révoquer la délégation à ${d.delegataire_nom} ?`)) return;
    this.service.revoquerDelegation(d.id).subscribe({
      next: () => { this.toast.success('Délégation révoquée.'); this.charger(); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }
}
