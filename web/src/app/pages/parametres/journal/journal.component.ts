// src/app/pages/parametres/journal/journal.component.ts
//
// Journal d'activité : opérations de paramétrage, délégations, réaffectations,
// retraits de pièces… (administrateurs et contrôleurs).

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { DemandesService } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

const TYPES_OBJETS: Record<string, string> = {
  'api.ParametreSysteme': 'Société', 'api.Agence': 'Agence', 'api.Service': 'Département', 'api.Poste': 'Poste',
  'api.Fonction': 'Fonction', 'api.Categoriesalarie': 'Catégorie de salarié', 'api.Statut': 'Statut', 'api.User': 'Utilisateur',
  'api.Responsabilite': 'Responsabilité', 'api.AffectationResponsabilite': 'Responsabilité attribuée',
  'api.PerimetreConsultation': 'Périmètre de consultation', 'api.JourFerie': 'Jour férié',
  'baremes.PerDiem': 'Barème · per diem', 'baremes.TarifKilometrique': 'Barème · tarif kilométrique',
  'baremes.TarifTransportVille': 'Barème · transport par ville', 'baremes.ForfaitTransportHorsPays': 'Barème · forfait hors pays',
  'baremes.TauxChange': 'Barème · taux de change', 'missions.Ville': 'Ville', 'missions.Pays': 'Pays', 'missions.Distance': 'Distance',
  'workflow.VersionWorkflow': 'Circuit de validation', 'workflow.Workflow': 'Circuit de validation', 'workflow.Tache': 'Validation',
  'workflow.Delegation': 'Délégation', 'demandes.TypeDemande': 'Type de demande', 'demandes.ChampType': 'Champ de formulaire',
  'demandes.ExigencePiece': 'Pièce exigée', 'demandes.TypePiece': 'Type de pièce', 'demandes.Document': 'Pièce jointe',
  'demandes.Demande': 'Demande',
};

@Component({
  selector: 'app-journal',
  templateUrl: './journal.component.html',
})
export class JournalComponent implements OnInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Date', champ: 'horodatage', format: 'dateheure' }, { libelle: 'Auteur', champ: l => l.auteur_nom || 'Système' },
    { libelle: 'Pour le compte de', champ: 'pour_compte_de_nom' },
    { libelle: 'Opération', champ: l => this.libelles[l.action] || l.action }, { libelle: 'Objet', champ: 'objet_libelle' },
    { libelle: "Type d'objet", champ: l => this.typeObjet(l.objet_type) || l.objet_type }, { libelle: 'Identifiant', champ: 'objet_id' }, { libelle: 'Motif', champ: 'motif' },
  ];
  get paramsExport(): Record<string, any> { return { ...this.filtres }; }

  private readonly service = inject(DemandesService);
  private readonly toast = inject(ToastrService);

  lignes: any[] = [];
  total = 0;
  page = 1;
  filtres = { du: '', au: '', action: '', search: '' };
  detail: any = null;
  chargement = false;

  readonly libelles: Record<string, string> = {
    'parametrage.creation': 'Paramétrage — création', 'parametrage.modification': 'Paramétrage — modification',
    'parametrage.suppression': 'Paramétrage — suppression', 'workflow.version_creee': 'Circuit — nouvelle version',
    'workflow.publication': 'Circuit — publication', 'workflow.brouillon_supprime': 'Circuit — brouillon supprimé',
    'workflow.reaffectation': 'Validation réaffectée', 'delegation.creation': 'Délégation créée',
    'delegation.revocation': 'Délégation révoquée', 'document.retrait': 'Pièce retirée',
    'bareme.creation': 'Barème — nouvelle valeur', 'bareme.suppression': 'Barème — valeur à venir supprimée',
  };

  ngOnInit(): void { this.charger(); }

  charger(page = 1): void {
    this.page = page;
    this.chargement = true;
    this.service.journal({ ...this.filtres, page }).subscribe({
      next: r => { this.lignes = r.results; this.total = r.count; this.chargement = false; },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  private minuterie: any;
  rechercher(): void { clearTimeout(this.minuterie); this.minuterie = setTimeout(() => this.charger(), 300); }
  effacerFiltres(): void { this.filtres = { du: '', au: '', action: '', search: '' }; this.charger(); }

  /** Nature de l'objet en clair (le nom technique du modèle n'aide pas le lecteur) */
  typeObjet(t: string): string { return TYPES_OBJETS[t] ?? ''; }

  json(v: any): string { return v ? JSON.stringify(v, null, 2) : '—'; }
}
