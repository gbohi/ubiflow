// src/app/pages/demandes/champs-demande/champs-demande.component.ts
//
// Formulaire d'une demande : objet, montant et champs paramétrés du type
// (saisie ou lecture). Le contenu est modifié en place dans `contenu`.

import { Component, Input, OnChanges, inject } from '@angular/core';
import { ChampType } from 'src/app/core/services/demandes/demandes.service';
import { OrganisationService } from 'src/app/core/services/organisation/organisation.service';

export interface ContenuDemande { objet: string; montant_demande: any; devise: string; donnees: Record<string, any>; }

@Component({
  selector: 'app-champs-demande',
  templateUrl: './champs-demande.component.html',
})
export class ChampsDemandeComponent implements OnChanges {
  private readonly organisation = inject(OrganisationService);

  @Input({ required: true }) contenu!: ContenuDemande;
  @Input() champs: ChampType[] = [];
  @Input() avecMontant = true;
  @Input() lectureSeule = false;
  /** Faux : seulement les champs du type (corrections d'un valideur) */
  @Input() avecObjet = true;
  /** Exemple affiché dans le champ Objet (selon le type de demande) */
  @Input() exempleObjet = 'Résumez la demande en quelques mots';
  /** Erreurs renvoyées par l'API : { objet, montant_demande, donnees: { code: message } } */
  @Input() erreurs: any = null;

  collaborateurs: { id: number; libelle: string }[] = [];
  private collaborateursCharges = false;

  ngOnChanges(): void {
    if (!this.collaborateursCharges && this.champs.some(c => c.nature === 'collaborateur')) {
      this.collaborateursCharges = true;
      this.organisation.annuaire().subscribe(u => this.collaborateurs = (u ?? []).map(x => ({ id: x.id, libelle: x.libelle })));
    }
  }

  erreur(code: string): string | null {
    const e = this.erreurs?.donnees?.[code];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }

  erreurDirecte(cle: string): string | null {
    const e = this.erreurs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }

  /** Valeur affichée en lecture seule */
  affichage(c: ChampType): string {
    const v = this.contenu.donnees?.[c.code];
    if (v === null || v === undefined || v === '') return '—';
    if (c.nature === 'booleen') return v ? 'Oui' : 'Non';
    if (c.nature === 'date') return new Date(v).toLocaleDateString('fr-FR');
    if (c.nature === 'datetime') return new Date(v).toLocaleString('fr-FR');
    if (c.nature === 'montant') return Number(v).toLocaleString('fr-FR').replace(/[\u202f\s]/g, '\u00a0');
    if (c.nature === 'collaborateur') return this.collaborateurs.find(x => x.id === Number(v))?.libelle ?? `#${v}`;
    return String(v);
  }
}
