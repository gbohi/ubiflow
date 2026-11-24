// src/app/pages/demandes/mission-form/mission-form.component.ts
//
// Saisie d'une mission (locale ou hors pays) avec l'estimation des frais
// recalculée en direct ; en lecture seule : informations et récapitulatif figé.
// L'objet `mission` est modifié en place (envoyé tel quel à l'API).

import { Component, DestroyRef, Input, OnChanges, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subject, debounceTime, switchMap, catchError, of } from 'rxjs';
import {
  BaremesService, Calcul, FRAIS_PAR_TYPE, MOYENS_TRANSPORT, RUBRIQUES_FRAIS, Ville,
} from 'src/app/core/services/baremes/baremes.service';

/** ISO (avec fuseau) → valeur d'un champ datetime-local */
export function versSaisie(v: string | null | undefined): string {
  if (!v) return '';
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const z = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${z(d.getMonth() + 1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}`;
}

@Component({
  selector: 'app-mission-form',
  templateUrl: './mission-form.component.html',
})
export class MissionFormComponent implements OnInit, OnChanges {
  private readonly service = inject(BaremesService);
  private readonly destroyRef = inject(DestroyRef);

  @Input({ required: true }) mission!: Record<string, any>;
  @Input({ required: true }) typeDemande!: number;
  @Input() typeMission: 'locale' | 'hors_pays' = 'locale';
  @Input() demandeId: number | null = null;
  @Input() lectureSeule = false;
  /** Calcul figé (lecture seule) */
  @Input() calculFige: Calcul | null = null;
  /** Erreurs de l'API : { mission: { champ: message }, calcul: [...] } */
  @Input() erreurs: any = null;

  villes: Ville[] = [];
  calcul: Calcul | null = null;
  calculEnCours = false;
  readonly moyens = MOYENS_TRANSPORT;
  readonly rubriques = RUBRIQUES_FRAIS;
  private readonly recalcul$ = new Subject<void>();
  private preparee: any = null;

  ngOnInit(): void {
    this.service.villes().subscribe(v => this.villes = v);
    this.recalcul$.pipe(
      debounceTime(400),
      switchMap(() => { this.calculEnCours = true;
        return this.service.calculer(this.typeDemande, this.mission, this.demandeId).pipe(catchError(() => of(null))); }),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(c => { this.calcul = c; this.calculEnCours = false; });
  }

  ngOnChanges(): void {
    if (!this.mission || this.mission === this.preparee) return;
    this.preparee = this.mission;
    this.mission['trajet'] ??= 'aller_retour';
    this.mission['frais'] ??= [];
    this.mission['moyen_transport'] ??= this.typeMission === 'hors_pays' ? 'avion' : 'transport_commun';
    this.mission['depart_le'] = versSaisie(this.mission['depart_le']);
    this.mission['retour_le'] = versSaisie(this.mission['retour_le']);
    if (!this.lectureSeule) setTimeout(() => this.changer());
  }

  get villesDepart(): Ville[] {
    const pays = this.paysLocal;
    return pays ? this.villes.filter(v => v.pays_code === pays) : this.villes;
  }

  /** Pays de la ville de départ (pays des missions locales) */
  get paysLocal(): string | null {
    const depart = this.villes.find(v => v.id === this.mission['ville_depart']);
    return depart?.pays_code ?? (this.villes.some(v => v.pays_code === 'CI') ? 'CI' : null);
  }

  get villesDestination(): Ville[] {
    const pays = this.paysLocal;
    if (!pays) return this.villes;
    return this.villes.filter(v => this.typeMission === 'locale' ? v.pays_code === pays : v.pays_code !== pays);
  }

  get rubriquesAutorisees(): string[] { return FRAIS_PAR_TYPE[this.typeMission]; }

  get distanceReferentiel(): number | null | undefined { return this.calcul?.mission?.distance_referentiel_km; }

  libelleVille(v: Ville): string { return this.typeMission === 'hors_pays' ? `${v.libelle} (${v.pays_libelle})` : v.libelle; }

  /** Ville de destination sans tarif de transport : montant saisi avec justification */
  transportManuel(): boolean {
    const m = this.mission['montant_transport_manuel'];
    return (m !== null && m !== undefined && m !== '')
      || !!this.calcul?.erreurs.some(e => e.startsWith('Aucun tarif de transport'));
  }

  rechercheVille = (terme: string, v: Ville) =>
    `${v.libelle} ${v.pays_libelle}`.toLowerCase().includes(terme.toLowerCase());

  changer(): void { if (!this.lectureSeule) this.recalcul$.next(); }

  ajouterFrais(): void {
    (this.mission['frais'] as any[]).push({ rubrique: this.rubriquesAutorisees[0], montant: null, devise: 'XOF', description: '' });
  }

  retirerFrais(i: number): void { (this.mission['frais'] as any[]).splice(i, 1); this.changer(); }

  erreur(cle: string): string | null {
    const e = this.erreurs?.mission?.[cle] ?? this.calcul?.champs?.[cle];
    return e ? (Array.isArray(e) ? e.join(' ') : String(e)) : null;
  }

  get erreursCalcul(): string[] {
    const e = this.erreurs?.calcul;
    return Array.isArray(e) ? e : [];
  }

  // ── Lecture seule ──
  libelleMoyen(code: string): string { return this.moyens.find(m => m.code === code)?.libelle ?? code ?? '—'; }
  dateHeure(v: string): string { return v ? new Date(v).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '—'; }
}
