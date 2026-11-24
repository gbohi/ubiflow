// src/app/account/login/login.component.ts
import { Component, OnInit, DestroyRef, inject } from '@angular/core';
import { UntypedFormBuilder, UntypedFormGroup, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Store } from '@ngrx/store';
import { Actions, ofType } from '@ngrx/effects';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { TokenStorageService } from 'src/app/core/services/token-storage.service';
import { Souvenir, SouvenirService, initialesSouvenir } from 'src/app/core/services/souvenir.service';
import { login, loginFailure, loginSuccess } from 'src/app/store/Authentication/authentication.actions';

@Component({
  selector: 'app-login',
  templateUrl: './login.component.html',
  styleUrls: ['./login.component.scss']
})
export class LoginComponent implements OnInit {

  loginForm!: UntypedFormGroup;
  submitted = false;
  fieldTextType = false;
  isLoading = false;
  errorMessage: string | null = null;

  private destroyRef = inject(DestroyRef);
  private souvenirs = inject(SouvenirService);

  /** Utilisateur mémorisé (« Se souvenir de moi ») : carte « Bon retour » */
  souvenir: Souvenir | null = null;

  constructor(
    private formBuilder: UntypedFormBuilder,
    private route: ActivatedRoute,
    private router: Router,
    private store: Store,
    private actions$: Actions,
    private tokenStorage: TokenStorageService,
  ) {}

  ngOnInit(): void {
    // Formulaire créé d'abord : le gabarit en a besoin même en cas de redirection
    this.souvenir = this.souvenirs.lire();
    this.loginForm = this.formBuilder.group({
      username: [this.souvenir?.matricule ?? '', [Validators.required]],
      password: ['', [Validators.required]],
      souvenir: [!!this.souvenir],
    });

    // Déjà connecté → aller à la page demandée (ou à l'accueil)
    if (this.tokenStorage.getAccessToken()) {
      this.router.navigateByUrl(this.destinationApresConnexion());
      return;
    }

    // Utilisateur mémorisé : le curseur va directement au mot de passe
    if (this.souvenir) setTimeout(() => document.getElementById('password-input')?.focus());

    // Erreur de connexion → afficher le message
    this.actions$.pipe(
      ofType(loginFailure),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(({ error }) => {
      this.errorMessage = error;
      this.isLoading = false;
    });

    // Connexion réussie → rediriger
    this.actions$.pipe(
      ofType(loginSuccess),
      takeUntilDestroyed(this.destroyRef)
    ).subscribe(({ user }) => {
      // Matricule (et nom de la carte) mémorisés ou oubliés selon la case ; jamais le mot de passe
      const u: any = user || {};
      if (this.f['souvenir'].value) {
        const nom = [u.nom, u.prenom].filter(Boolean).join(' ');
        this.souvenirs.enregistrer(u.username || this.f['username'].value.trim(), nom);
      } else {
        this.souvenirs.oublier();
      }
      this.router.navigateByUrl(this.destinationApresConnexion());
    });
  }

  /**
   * Page demandée avant la connexion : uniquement une adresse interne
   * (« /… » mais pas « //… », qui pointerait vers un autre site).
   */
  private destinationApresConnexion(): string {
    const url: string = this.route.snapshot.queryParams['returnUrl'] || '';
    const interne = url.startsWith('/') && !url.startsWith('//') && !url.startsWith('/auth/');
    return interne ? url : '/';
  }

  get f() { return this.loginForm.controls; }

  onSubmit(): void {
    this.submitted = true;
    this.errorMessage = null;
    if (this.loginForm.invalid) return;
    this.isLoading = true;
    this.store.dispatch(login({
      username: this.f['username'].value,
      password: this.f['password'].value,
    }));
  }

  /** Prénom pour « Bon retour, Fatou » (dernier mot du nom affiché) */
  get prenomSouvenir(): string {
    const mots = (this.souvenir?.nom ?? '').trim().split(/\s+/).filter(Boolean);
    return mots.length >= 2 ? mots[mots.length - 1] : (mots[0] ?? '');
  }

  get initiales(): string { return this.souvenir ? initialesSouvenir(this.souvenir.nom, this.souvenir.matricule) : ''; }

  /** « Changer » : oublie le matricule mémorisé et réaffiche le formulaire complet */
  changerDeCompte(): void {
    this.souvenirs.oublier();
    this.souvenir = null;
    this.errorMessage = null;
    this.submitted = false;
    this.loginForm.patchValue({ username: '', password: '', souvenir: false });
    setTimeout(() => document.getElementById('username')?.focus());
  }

  toggleFieldTextType(): void {
    this.fieldTextType = !this.fieldTextType;
  }
}
