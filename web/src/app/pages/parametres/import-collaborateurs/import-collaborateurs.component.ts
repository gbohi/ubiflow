// src/app/pages/parametres/import-collaborateurs/import-collaborateurs.component.ts
//
// Import Excel des collaborateurs : modèle, simulation (contrôle sans rien
// enregistrer), import réel et rapport ligne par ligne.

import { Component, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import {
  ImportCollaborateurs, LigneRapportImport, OrganisationService, aujourdhui, messageErreur,
} from 'src/app/core/services/organisation/organisation.service';

@Component({
  selector: 'app-import-collaborateurs',
  templateUrl: './import-collaborateurs.component.html',
})
export class ImportCollaborateursComponent implements OnInit {
  private readonly organisation = inject(OrganisationService);
  private readonly toast = inject(ToastrService);

  @ViewChild('champFichier') champFichier?: ElementRef<HTMLInputElement>;

  fichier: File | null = null;
  dateEffet = aujourdhui();
  enCours = false;
  resultat: ImportCollaborateurs | null = null;
  historique: ImportCollaborateurs[] = [];
  filtre: '' | LigneRapportImport['resultat'] = '';

  readonly libelles: Record<string, string> = {
    cree: 'Créé', mis_a_jour: 'Mis à jour', inchange: 'Inchangé', rejete: 'Rejeté',
  };
  readonly classes: Record<string, string> = {
    cree: 't-ve', mis_a_jour: 't-bl', inchange: 't-gr', rejete: 't-ro',
  };

  ngOnInit(): void { this.chargerHistorique(); }

  chargerHistorique(): void {
    this.organisation.imports().subscribe({ next: h => this.historique = h, error: () => {} });
  }

  telechargerModele(): void {
    this.organisation.modeleImport().subscribe({
      next: blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'modele-import-collaborateurs.xlsx';
        a.click();
        URL.revokeObjectURL(url);
      },
      error: e => this.toast.error(messageErreur(e, 'Téléchargement impossible.')),
    });
  }

  choisir(evt: Event): void {
    const f = (evt.target as HTMLInputElement).files?.[0] ?? null;
    this.resultat = null;
    if (f && !f.name.toLowerCase().endsWith('.xlsx')) {
      this.toast.error('Choisissez un fichier Excel (.xlsx).');
      this.fichier = null;
      return;
    }
    this.fichier = f;
  }

  lancer(simulation: boolean): void {
    if (!this.fichier || this.enCours) return;
    if (!simulation && !confirm("Importer réellement ce fichier ? Les collaborateurs seront créés ou mis à jour.")) return;
    this.enCours = true;
    this.organisation.importer(this.fichier, this.dateEffet, simulation).subscribe({
      next: r => {
        this.enCours = false;
        this.resultat = r;
        this.filtre = r.nb_rejetes ? 'rejete' : '';
        this.chargerHistorique();
        if (simulation) {
          this.toast.info('Simulation terminée : rien n\'a été enregistré.');
        } else {
          this.toast.success(`Import terminé : ${r.nb_crees} créé(s), ${r.nb_mis_a_jour} mis à jour, ${r.nb_rejetes} rejeté(s).`);
          this.fichier = null;
          if (this.champFichier) this.champFichier.nativeElement.value = '';
        }
      },
      error: e => { this.enCours = false; this.toast.error(messageErreur(e, 'Import impossible.')); },
    });
  }

  voir(imp: ImportCollaborateurs): void {
    this.resultat = imp;
    this.filtre = '';
  }

  get lignes(): LigneRapportImport[] {
    const r = this.resultat?.rapport ?? [];
    return this.filtre ? r.filter(l => l.resultat === this.filtre) : r;
  }
}
