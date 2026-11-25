// src/app/pages/dashboards/accueil/accueil.component.ts
//
// Accueil de synthèse : comprendre en quelques secondes ce qui se passe et ce
// qu'il faut faire. Phrase de synthèse, barre d'actions unique, 4 indicateurs,
// bloc « À faire maintenant » (tout ce qui attend une action, les plus anciens
// d'abord), listes et graphiques de la vue, notifications et activité récente
// groupée par demande.

import { Component, OnInit, QueryList, ViewChildren, inject } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { ToastrService } from 'ngx-toastr';
import { firstValueFrom } from 'rxjs';
import {
  Cellule, chargerLogoPdf, enregistrerPdf, exporterExcel, imagePdf, nomFichier, nouveauPdf, placePdf, tableauPdf,
} from 'src/app/core/helpers/exports';
import { BaremesService } from 'src/app/core/services/baremes/baremes.service';
import { CLASSES_STATUT, iconeType, teinteType } from 'src/app/core/services/demandes/demandes.service';
import { PilotageService } from 'src/app/core/services/pilotage/pilotage.service';
import { GrapheBarresComponent } from '../graphes/graphe-barres.component';
import { GrapheColonnesComponent } from '../graphes/graphe-colonnes.component';
import { complet } from '../graphes/format';
import { svgVersPng } from '../graphes/svg-png';

/** Un bloc de l'accueil prêt à exporter : titre, en-têtes, lignes, et le graphique éventuel */
interface BlocExport { titre: string; lignes: Cellule[][]; graphe?: string; }

@Component({
  selector: 'app-accueil',
  templateUrl: './accueil.component.html',
  host: { class: 'acc-page' },
})
export class AccueilComponent implements OnInit {
  private readonly service = inject(PilotageService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly toast = inject(ToastrService);
  private readonly baremes = inject(BaremesService);

  @ViewChildren(GrapheBarresComponent) private gBarres!: QueryList<GrapheBarresComponent>;
  @ViewChildren(GrapheColonnesComponent) private gColonnes!: QueryList<GrapheColonnesComponent>;
  exportEnCours = false;

  readonly classes = CLASSES_STATUT;
  readonly icone = iconeType;
  readonly teinte = teinteType;
  donnees: any = null;
  /** Heure de référence des « il y a… » (fixée au chargement : affichage stable) */
  private maintenant = Date.now();
  chargement = true;

  ngOnInit(): void { this.charger(this.route.snapshot.queryParamMap.get('profil') ?? undefined); }

  charger(profil?: string): void {
    this.chargement = true;
    this.service.accueil(profil).subscribe({
      next: d => { this.maintenant = Date.now(); this.donnees = d; this.chargement = false; },
      error: () => this.chargement = false,
    });
  }

  choisir(code: string): void {
    this.router.navigate([], { queryParams: { profil: code }, replaceUrl: true });
    this.charger(code);
  }

  get dateDuJour(): string {
    const d = this.donnees?.aujourdhui ? new Date(this.donnees.aujourdhui + 'T00:00:00') : new Date();
    const t = d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  valeur(k: any): string { return complet(Number(k.valeur)); }

  lien(chemin: string | null): { route: string; params: any } | null {
    if (!chemin) return null;
    const [route, requete] = chemin.split('?');
    const params: any = {};
    for (const p of (requete ?? '').split('&').filter(Boolean)) { const [c, v] = p.split('='); params[c] = v; }
    return { route, params };
  }

  ouvrir(chemin: string | null): void {
    const l = this.lien(chemin);
    if (l) this.router.navigate([l.route], { queryParams: l.params });
  }

  montant(v: any): string { return `${complet(Number(v))} ${this.donnees?.devise ?? ''}`; }

  /** Nouvelle demande d'un type donné (ou choix du type) */
  nouvelle(code: string | null): void {
    this.router.navigate(['/demandes/nouvelle'], { queryParams: code ? { code } : {} });
  }

  libelleMotif(e: any): { texte: string; classe: string } | null {
    if (e.retard) return { texte: 'En retard', classe: 'm-retard' };
    return ({ a_payer: { texte: 'À payer', classe: 'm-payer' }, a_corriger: { texte: 'À corriger', classe: 'm-retard' },
              reversement: { texte: 'Reversement', classe: 'm-retard' } } as any)[e.motif] ?? null;
  }

  /** Action principale (pleine) pour payer et clôturer, secondaire pour le reste */
  actionPrincipale(e: any): boolean { return ['a_payer', 'a_cloturer', 'a_corriger'].includes(e.motif); }

  resumeActivite(a: any): string[] {
    return a.compte.map((c: any) => c.nombre > 1 ? `${c.type} ×${c.nombre}` : c.type);
  }

  depuis(iso: string | null): string {
    if (!iso) return '';
    const min = Math.floor((this.maintenant - new Date(iso).getTime()) / 60000);
    if (min < 60) return min <= 1 ? "à l'instant" : `il y a ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `il y a ${h} h`;
    const j = Math.floor(h / 24);
    return j === 1 ? 'hier' : `il y a ${j} jours`;
  }

  // ── Export Excel / PDF de chaque bloc ──
  private dateHeure(iso: string | null): string {
    return iso ? new Date(iso).toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' }) : '';
  }

  /** Lignes d'un bloc : 'a_faire', 'liste:<clé>', 'graphe:<clé>', 'notifications', 'activites' */
  private bloc(cle: string): BlocExport | null {
    const d = this.donnees;
    if (!d) return null;
    const num = (v: any) => (v === null || v === undefined || v === '' ? null : Number(v));
    if (cle === 'a_faire') {
      return { titre: 'À faire maintenant', lignes: [['N°', 'Référence', 'Objet', 'Demandeur', 'Motif', 'Précision', `Montant (${d.devise})`, 'Depuis le', 'Action'],
        ...d.a_faire.map((e: any, i: number) => [i + 1, e.reference, e.objet, e.demandeur, this.libelleMotif(e)?.texte ?? '', e.info ?? '',
                                                 num(e.montant), this.dateHeure(e.depuis), e.action])] };
    }
    if (cle.startsWith('liste:')) {
      const l = d.listes.find((x: any) => x.cle === cle.slice(6));
      if (!l) return null;
      return { titre: l.titre, lignes: [['N°', 'Référence', 'Objet', 'Type', 'Demandeur', 'Statut', 'Précision', `Montant (${d.devise})`],
        ...l.lignes.map((x: any, i: number) => [i + 1, x.reference, x.objet, x.type, x.demandeur ?? '', x.statut_libelle, x.info ?? '', num(x.montant)])] };
    }
    if (cle.startsWith('graphe:')) {
      const g = d.graphes.find((x: any) => x.cle === cle.slice(7));
      if (!g) return null;
      const u = g.unite === 'montant' ? ` (${d.devise})` : '';
      const lignes: Cellule[][] = g.type === 'barres'
        ? [['Libellé', g.unite === 'montant' ? `Montant (${d.devise})` : 'Nombre'], ...g.donnees.map((x: any) => [x.libelle, Number(x.valeur)])]
        : [['Mois', ...g.series.map((x: any) => x.libelle + u)], ...g.donnees.map((x: any) => [x.libelle, ...g.series.map((sr: any) => Number(x.valeurs?.[sr.cle]) || 0)])];
      return { titre: g.titre, lignes, graphe: g.titre };
    }
    if (cle === 'notifications') {
      return { titre: 'Notifications', lignes: [['N°', 'Notification', 'Lue', 'Le'],
        ...d.notifications.map((n: any, i: number) => [i + 1, n.titre, n.lue ? 'Oui' : 'Non', this.dateHeure(n.creee_le)])] };
    }
    if (cle === 'activites') {
      return { titre: 'Activité récente', lignes: [['N°', 'Référence', 'Objet', 'Dernière action', 'Par', 'Le', 'Résumé'],
        ...d.activites.map((a: any, i: number) => [i + 1, a.reference, a.objet, a.derniere.type, a.derniere.auteur, this.dateHeure(a.derniere.le),
                                                   this.resumeActivite(a).join(', ')])] };
    }
    return null;
  }

  private get sousTitreExport(): string {
    const profil = this.donnees?.profils?.find((p: any) => p.code === this.donnees.profil)?.libelle;
    return `Accueil${profil ? ' — vue ' + profil : ''} · ${this.donnees?.prenom ?? ''} · édité le ${new Date().toLocaleString('fr-FR')}`;
  }

  exporterBlocExcel(cle: string): void {
    const b = this.bloc(cle);
    if (!b) return;
    exporterExcel(nomFichier('accueil', b.titre, new Date().toISOString().slice(0, 10)),
      [{ nom: b.titre, lignes: [[b.titre], [this.sousTitreExport], [], ...b.lignes] }]);
  }

  async exporterBlocPdf(cle: string): Promise<void> {
    const b = this.bloc(cle);
    if (!b || this.exportEnCours) return;
    this.exportEnCours = true;
    try {
      await chargerLogoPdf((await firstValueFrom(this.baremes.parametres()).catch(() => null))?.logo);
      const p = nouveauPdf(b.titre, this.sousTitreExport, b.lignes[0].length > 6);
      if (b.graphe) {
        const svg = [...this.gBarres.toArray(), ...this.gColonnes.toArray()].find(g => g.titre === b.graphe)?.svg.nativeElement;
        if (svg) await imagePdf(p, await svgVersPng(svg));
        placePdf(p, 20);
      }
      const corps = b.lignes.slice(1);
      tableauPdf(p, b.lignes[0], corps.map(l => l.map((c, i) => typeof c === 'number' && i > 0 ? complet(c) : c)), false,
                 b.lignes[0].map((_, i) => i).filter(i => i > 0 && corps.some(l => typeof l[i] === 'number')));
      enregistrerPdf(p, nomFichier('accueil', b.titre, new Date().toISOString().slice(0, 10)));
    } catch (e: any) {
      this.toast.error(e?.message || "L'export a échoué.");
    } finally {
      this.exportEnCours = false;
    }
  }
}
