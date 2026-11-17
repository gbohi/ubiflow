// Mon équipe : comptes du prestataire. Le responsable crée, modifie et
// désactive ses agents de comptoir et choisit leurs agences d'intervention
// (UbiPharm peut aussi le faire depuis Paramètres › Utilisateurs).
import { Component, DestroyRef, OnInit, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { ToastrService } from 'ngx-toastr';
import {
  AgencePresta, EspacePrestataireService, MembreEquipe, couleur, initiales, messageErreur, nombreFr,
} from 'src/app/core/services/espace-prestataire/espace-prestataire.service';

interface FicheAgent {
  id: number | null; nom: string; prenom: string; username: string; contact: string; email: string;
  password: string; password2: string; agences: Set<number>;
}

@Component({
  selector: 'app-equipe-prestataire',
  templateUrl: './equipe.component.html',
})
export class EquipeComponent implements OnInit {
  private api = inject(EspacePrestataireService);
  private toastr = inject(ToastrService);
  private destroyRef = inject(DestroyRef);

  @ViewChild('ficheModal', { static: false }) ficheModal?: ModalDirective;
  @ViewChild('mdpModal', { static: false }) mdpModal?: ModalDirective;

  membres: MembreEquipe[] = [];
  agencesPresta: AgencePresta[] = [];
  chargement = true;
  erreur: string | null = null;

  fiche: FicheAgent | null = null;
  ficheErreur: string | null = null;
  envoi = false;
  mdpPour: MembreEquipe | null = null;
  mdp = { password: '', password2: '' };
  mdpErreur: string | null = null;

  readonly initiales = initiales;
  readonly couleur = couleur;
  readonly nombreFr = nombreFr;

  ngOnInit(): void {
    this.api.contexte().pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: c => this.agencesPresta = c.agences ?? [], error: () => {} });
    this.charger();
  }

  charger(): void {
    this.api.equipe().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: m => { this.membres = m ?? []; this.chargement = false; },
      error: e => { this.erreur = messageErreur(e, 'L\'équipe n\'a pas pu être chargée.'); this.chargement = false; },
    });
  }

  get actifs(): number { return this.membres.filter(m => m.is_active).length; }
  get retraitsJour(): number { return this.membres.reduce((s, m) => s + (m.retraits_aujourdhui || 0), 0); }

  agencesTexte(m: MembreEquipe): string {
    if (m.role !== 'agent_comptoir') return 'Toutes';
    return m.agences?.length ? m.agences.map(a => a.nom).join(', ') : 'Toutes les agences';
  }

  // ── Création / modification ─────────────────────────────────
  nouveau(): void {
    this.fiche = { id: null, nom: '', prenom: '', username: '', contact: '', email: '', password: '', password2: '',
                   agences: new Set(this.agencesPresta.length === 1 ? [this.agencesPresta[0].id] : []) };
    this.ficheErreur = null;
    this.ficheModal?.show();
  }

  modifier(m: MembreEquipe): void {
    this.fiche = { id: m.id, nom: m.nom, prenom: m.prenom, username: m.username, contact: m.contact || '',
                   email: m.email || '', password: '', password2: '',
                   agences: new Set((m.agences ?? []).map(a => a.id)) };
    this.ficheErreur = null;
    this.ficheModal?.show();
  }

  basculerAgence(id: number): void {
    if (!this.fiche) return;
    this.fiche.agences.has(id) ? this.fiche.agences.delete(id) : this.fiche.agences.add(id);
  }

  genererMotDePasse(cible: { password: string; password2: string }): void {
    const lettres = 'abcdefghjkmnpqrstuvwxyz', maj = 'ABCDEFGHJKLMNPQRSTUVWXYZ', chiffres = '23456789', spe = '#@!$%';
    const tirer = (s: string) => s[Math.floor(Math.random() * s.length)];
    const mdp = tirer(maj) + Array.from({ length: 6 }, () => tirer(lettres)).join('') + tirer(chiffres) + tirer(chiffres) + tirer(spe);
    cible.password = mdp;
    cible.password2 = mdp;
  }

  enregistrer(): void {
    const f = this.fiche;
    if (!f || this.envoi) return;
    if (!f.agences.size) { this.ficheErreur = "Cochez au moins une agence d'intervention."; return; }
    this.envoi = true;
    this.ficheErreur = null;
    const agences = [...f.agences];
    const requete = f.id
      ? this.api.modifierAgent(f.id, { nom: f.nom, prenom: f.prenom, contact: f.contact, email: f.email, agences })
      : this.api.creerAgent({ nom: f.nom, prenom: f.prenom, username: f.username, contact: f.contact, email: f.email,
                              password: f.password, password2: f.password2, agences });
    requete.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: m => {
        this.envoi = false;
        this.ficheModal?.hide();
        this.toastr.success(f.id ? `${m.nom_complet} : compte mis à jour.`
          : `Compte de ${m.nom_complet} créé. Identifiant : ${m.username}`, 'Mon équipe');
        this.charger();
      },
      error: e => { this.envoi = false; this.ficheErreur = messageErreur(e, 'Enregistrement impossible.'); },
    });
  }

  basculerActif(m: MembreEquipe): void {
    if (m.is_active && !confirm(`Désactiver le compte de ${m.nom_complet} ? Il ne pourra plus se connecter.`)) return;
    this.api.modifierAgent(m.id, { is_active: !m.is_active }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: r => { this.toastr.success(`${r.nom_complet} : compte ${r.is_active ? 'réactivé' : 'désactivé'}.`, 'Mon équipe'); this.charger(); },
      error: e => this.toastr.error(messageErreur(e, 'Modification impossible.'), 'Mon équipe'),
    });
  }

  // ── Mot de passe ────────────────────────────────────────────
  ouvrirMotDePasse(m: MembreEquipe): void {
    this.mdpPour = m;
    this.mdp = { password: '', password2: '' };
    this.mdpErreur = null;
    this.mdpModal?.show();
  }

  enregistrerMotDePasse(): void {
    const m = this.mdpPour;
    if (!m || this.envoi) return;
    this.envoi = true;
    this.api.motDePasseAgent(m.id, this.mdp.password, this.mdp.password2).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: r => { this.envoi = false; this.mdpModal?.hide(); this.toastr.success(r.detail, 'Mon équipe'); },
      error: e => { this.envoi = false; this.mdpErreur = messageErreur(e, 'Mot de passe refusé.'); },
    });
  }
}
