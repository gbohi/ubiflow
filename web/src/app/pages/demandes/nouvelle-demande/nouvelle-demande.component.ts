// src/app/pages/demandes/nouvelle-demande/nouvelle-demande.component.ts
//
// Nouvelle demande : choix du type, saisie, enregistrement en brouillon
// (la soumission se fait depuis la fiche, après vérification du circuit).

import { Component, OnInit, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { DemandesService, TypeDemande, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ContenuDemande } from '../champs-demande/champs-demande.component';

@Component({
  selector: 'app-nouvelle-demande',
  templateUrl: './nouvelle-demande.component.html',
})
export class NouvelleDemandeComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastrService);

  readonly icone = iconeType;
  readonly teinte = teinteType;
  types: TypeDemande[] = [];
  type: TypeDemande | null = null;
  contenu: ContenuDemande = { objet: '', montant_demande: null, devise: 'XOF', donnees: {} };
  mission: Record<string, any> = {};
  erreurs: any = null;
  enCours = false;
  chargement = true;

  ngOnInit(): void {
    this.service.types().subscribe({
      next: t => {
        this.types = t.filter(x => x.circuit_publie);
        this.chargement = false;
        const id = Number(this.route.snapshot.queryParamMap.get('type'));
        const choisi = this.types.find(x => x.id === id) ?? (this.types.length === 1 ? this.types[0] : null);
        if (choisi) this.choisir(choisi);
      },
      error: e => { this.chargement = false; this.toast.error(messageErreur(e)); },
    });
  }

  /** Changement de type depuis le formulaire (la saisie propre à l'ancien type est abandonnée) */
  changerType(id: number): void {
    const t = this.types.find(x => x.id === id);
    if (t && t.id !== this.type?.id) {
      const objet = this.contenu.objet;
      this.choisir(t);
      this.contenu.objet = objet;
    }
  }

  choisir(t: TypeDemande): void {
    this.type = t;
    this.erreurs = null;
    this.contenu = { objet: '', montant_demande: null, devise: 'XOF', donnees: {} };
    this.mission = {};
  }

  get estMission(): boolean { return this.type?.famille === 'mission'; }
  get typeMission(): 'locale' | 'hors_pays' { return this.type?.parametres?.['type_mission'] ?? 'locale'; }

  /** Crée le brouillon ; avec soumettre=true, le soumet aussitôt. */
  enregistrer(soumettre = false): void {
    if (!this.type || this.enCours) return;
    if (soumettre && !confirm('Soumettre la demande pour validation ? Elle ne sera plus modifiable, sauf retour pour correction.')) return;
    this.enCours = true;
    this.erreurs = null;
    this.service.creer({ type_demande: this.type.id!, objet: this.contenu.objet, montant_demande: this.contenu.montant_demande,
                         donnees: this.contenu.donnees, ...(this.estMission ? { mission: this.mission } : {}) }).subscribe({
      next: d => {
        if (!soumettre) {
          this.toast.success('Brouillon enregistré.');
          this.router.navigate(['/demandes', d.id]);
          return;
        }
        this.service.soumettre(d.id).subscribe({
          next: s => {
            this.toast.success(`Demande ${s.reference} soumise.`);
            this.router.navigate(['/demandes', d.id]);
          },
          error: e => {
            // Le brouillon existe : on l'ouvre pour corriger ce qui bloque
            const circuit = e?.champs?.circuit;
            this.toast.error(Array.isArray(circuit) ? circuit.join(' ') : messageErreur(e, 'Vérifiez les informations saisies.'));
            this.toast.info('La demande est enregistrée en brouillon.');
            this.router.navigate(['/demandes', d.id]);
          },
        });
      },
      error: e => {
        this.enCours = false;
        this.erreurs = e?.champs ?? null;
        this.toast.error(messageErreur(e, 'Vérifiez les informations saisies.'));
      },
    });
  }
}
