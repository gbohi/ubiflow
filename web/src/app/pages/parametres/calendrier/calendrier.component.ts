// src/app/pages/parametres/calendrier/calendrier.component.ts
//
// Calendrier des délais de validation : jours ouvrés de la semaine et jours fériés.

import { Component, OnInit, inject } from '@angular/core';
import { ToastrService } from 'ngx-toastr';
import { BaremesService, JourFerie } from 'src/app/core/services/baremes/baremes.service';
import { messageErreur } from 'src/app/core/services/organisation/organisation.service';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-calendrier',
  templateUrl: './calendrier.component.html',
})
export class CalendrierComponent implements OnInit {
  private readonly service = inject(BaremesService);
  private readonly toast = inject(ToastrService);

  readonly jours = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];
  readonly colonnesExport: ColonneExport[] = [
    { libelle: 'Date', champ: 'date', format: 'date' }, { libelle: 'Jour', champ: (j: JourFerie) => this.jourSemaine(j.date) },
    { libelle: 'Libellé', champ: 'libelle' },
  ];
  ouvres = new Set<number>([0, 1, 2, 3, 4]);
  annee = new Date().getFullYear();
  feries: JourFerie[] = [];
  nouveau: JourFerie = { date: '', libelle: '' };
  erreurs: any = null;

  ngOnInit(): void {
    this.service.parametres().subscribe(p => this.ouvres = new Set(p.jours_ouvres?.length ? p.jours_ouvres : [0, 1, 2, 3, 4]));
    this.charger();
  }

  charger(): void { this.service.joursFeries(this.annee).subscribe(f => this.feries = f); }
  changerAnnee(delta: number): void { this.annee += delta; this.charger(); }

  basculer(j: number): void {
    const s = new Set(this.ouvres);
    s.has(j) ? s.delete(j) : s.add(j);
    if (!s.size) { this.toast.warning('Au moins un jour ouvré.'); return; }
    this.service.enregistrerParametres({ jours_ouvres: [...s].sort() }).subscribe({
      next: () => { this.ouvres = s; this.toast.success('Jours ouvrés enregistrés.'); },
      error: e => this.toast.error(messageErreur(e)),
    });
  }

  ajouter(): void {
    this.erreurs = null;
    this.service.ajouterJourFerie(this.nouveau).subscribe({
      next: j => { this.nouveau = { date: '', libelle: '' }; this.toast.success('Jour férié ajouté.');
                   if (j.date.startsWith(String(this.annee))) this.charger(); },
      error: e => { this.erreurs = e?.champs ?? null; this.toast.error(messageErreur(e, 'Vérifiez la date et le libellé.')); },
    });
  }

  supprimer(j: JourFerie): void {
    if (!confirm(`Supprimer « ${j.libelle} » ?`)) return;
    this.service.supprimerJourFerie(j.id!).subscribe({ next: () => this.charger(), error: e => this.toast.error(messageErreur(e)) });
  }

  jourSemaine(iso: string): string { return this.jours[(new Date(`${iso}T00:00:00`).getDay() + 6) % 7]; }
}
