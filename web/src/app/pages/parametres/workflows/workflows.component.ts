// src/app/pages/parametres/workflows/workflows.component.ts
//
// Circuits de validation : par type de demande, version publiée, brouillon
// en cours et versions archivées.

import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { DemandesService, TypeDemande, VersionWorkflow } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-workflows',
  templateUrl: './workflows.component.html',
})
export class WorkflowsComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);

  types: TypeDemande[] = [];
  type: TypeDemande | null = null;
  versions: VersionWorkflow[] = [];

  ngOnInit(): void {
    this.service.types(true).subscribe(t => {
      this.types = t;
      const id = Number(this.route.snapshot.queryParamMap.get('type'));
      this.choisir(t.find(x => x.id === id) ?? t[0] ?? null);
    });
  }

  choisir(t: TypeDemande | null): void {
    this.type = t;
    this.versions = [];
    if (!t) return;
    this.router.navigate([], { queryParams: { type: t.id }, replaceUrl: true });
    this.service.versionsWorkflow(t.id).subscribe(v => this.versions = v);
  }

  get publiee() { return this.versions.find(v => v.etat === 'publiee'); }
  get brouillon() { return this.versions.find(v => v.etat === 'brouillon'); }
  get archivees() { return this.versions.filter(v => v.etat === 'archivee'); }

  nouvelle(source?: VersionWorkflow): void {
    if (!this.type) return;
    this.service.nouvelleVersion(this.type.id!, source?.id).subscribe({
      next: v => this.router.navigate(['/parametres/workflows', v.id]),
      error: e => this.toast.error(messageErreur(e)),
    });
  }
}
