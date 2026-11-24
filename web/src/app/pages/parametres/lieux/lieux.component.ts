// src/app/pages/parametres/lieux/lieux.component.ts
//
// Référentiel des lieux des missions : pays, villes et distances routières
// validées entre villes d'un même pays (calcul du transport en véhicule personnel).

import { Component, OnInit, ViewChild, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import { BaremesService, Distance, Pays, Ville } from 'src/app/core/services/baremes/baremes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { aUnRole } from 'src/app/core/helpers/roles';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

type Onglet = 'villes' | 'distances' | 'pays';

@Component({
  selector: 'app-lieux',
  templateUrl: './lieux.component.html',
})
export class LieuxComponent implements OnInit {
  private readonly service = inject(BaremesService);
  private readonly toast = inject(ToastrService);
  private readonly tokens = inject(TokenStorageService);

  onglet: Onglet = 'villes';
  pays: Pays[] = [];
  villes: Ville[] = [];
  distances: Distance[] = [];
  paysFiltre: number | null = null;
  recherche = '';
  readonly ecriture: boolean;

  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;
  fichePays: Pays = { code_iso: '', libelle: '', devise_usuelle: '', actif: true };
  ficheVille: Ville = { libelle: '', pays: 0, actif: true };
  ficheDistance: Distance = { ville_a: 0, ville_b: 0, km: 0 };
  erreurs: any = null;
  enCours = false;

  constructor() {
    this.ecriture = aUnRole(this.tokens.getUser(), ['super_admin', 'admin', 'admin_finances']);
  }

  ngOnInit(): void {
    this.service.pays(true).subscribe(p => {
      this.pays = p;
      this.paysFiltre ??= p.find(x => x.code_iso === 'CI')?.id ?? p[0]?.id ?? null;
      this.chargerVilles();
    });
    this.chargerDistances();
  }

  chargerPays(): void { this.service.pays(true).subscribe(p => this.pays = p); }
  chargerVilles(): void {
    this.service.villes({ pays: this.paysFiltre ?? undefined, tous: 1 }).subscribe(v => this.villes = v);
  }
  chargerDistances(): void { this.service.distances().subscribe(d => this.distances = d); }

  get villesAffichees(): Ville[] {
    const t = this.recherche.trim().toLowerCase();
    return t ? this.villes.filter(v => v.libelle.toLowerCase().includes(t)) : this.villes;
  }
  get distancesAffichees(): Distance[] {
    const t = this.recherche.trim().toLowerCase();
    return t ? this.distances.filter(d => `${d.ville_a_libelle} ${d.ville_b_libelle}`.toLowerCase().includes(t)) : this.distances;
  }
  get villesActives(): Ville[] { return this.villes.filter(v => v.actif); }

  // ── Export de l'onglet affiché ──
  get titreExport(): string { return this.onglet === 'villes' ? 'Villes' : this.onglet === 'distances' ? 'Distances' : 'Pays'; }
  get lignesExport(): any[] {
    return this.onglet === 'villes' ? this.villesAffichees : this.onglet === 'distances' ? this.distancesAffichees : this.pays;
  }
  get colonnesExport(): ColonneExport[] {
    if (this.onglet === 'villes') return [{ libelle: 'Ville', champ: 'libelle' }, { libelle: 'Pays', champ: 'pays_libelle' },
                                         { libelle: 'Active', champ: 'actif', format: 'oui_non' }];
    if (this.onglet === 'distances') return [{ libelle: 'Ville A', champ: 'ville_a_libelle' }, { libelle: 'Ville B', champ: 'ville_b_libelle' },
                                            { libelle: 'Distance (km)', champ: 'km', format: 'montant' }];
    return [{ libelle: 'Pays', champ: 'libelle' }, { libelle: 'Code ISO', champ: 'code_iso' }, { libelle: 'Devise usuelle', champ: 'devise_usuelle' },
            { libelle: 'Villes', champ: 'nb_villes' }, { libelle: 'Actif', champ: 'actif', format: 'oui_non' }];
  }

  nouveau(objet?: any): void {
    this.erreurs = null;
    if (this.onglet === 'pays') this.fichePays = objet ? { ...objet } : { code_iso: '', libelle: '', devise_usuelle: '', actif: true };
    if (this.onglet === 'villes') this.ficheVille = objet ? { ...objet } : { libelle: '', pays: this.paysFiltre ?? 0, actif: true };
    if (this.onglet === 'distances') this.ficheDistance = objet ? { ...objet } : { ville_a: 0, ville_b: 0, km: 0 };
    this.ficheModal?.show();
  }

  enregistrer(): void {
    if (this.enCours) return;
    this.enCours = true;
    this.erreurs = null;
    const requete: Observable<unknown> = this.onglet === 'pays' ? this.service.enregistrerPays(this.fichePays)
      : this.onglet === 'villes' ? this.service.enregistrerVille(this.ficheVille)
      : this.service.enregistrerDistance(this.ficheDistance);
    requete.subscribe({
      next: () => {
        this.enCours = false;
        this.ficheModal?.hide();
        this.toast.success('Enregistré.');
        if (this.onglet === 'pays') this.chargerPays();
        if (this.onglet === 'villes') this.chargerVilles();
        if (this.onglet === 'distances') this.chargerDistances();
      },
      error: (e: any) => { this.enCours = false; this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e, 'Vérifiez la saisie.')); },
    });
  }

  supprimerDistance(d: Distance): void {
    if (!confirm(`Supprimer la distance ${d.ville_a_libelle} – ${d.ville_b_libelle} ?`)) return;
    this.service.supprimerDistance(d.id!).subscribe({ next: () => this.chargerDistances(), error: e => this.toast.error(messageErreur(e)) });
  }

  erreur(cle: string): string | null {
    const e = this.erreurs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }
}
