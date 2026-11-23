import { LOCALE_ID, NgModule } from '@angular/core';
import { registerLocaleData } from '@angular/common';
import localeFr from '@angular/common/locales/fr';
import { BrowserModule } from '@angular/platform-browser';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { HttpClient, HTTP_INTERCEPTORS, provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';
import { AppRoutingModule } from './app-routing.module';
import { LayoutsModule } from './layouts/layouts.module';
import { ToastrModule } from 'ngx-toastr';
import { TranslateModule, TranslateLoader } from '@ngx-translate/core';
import { TranslateHttpLoader } from '@ngx-translate/http-loader';
import { StoreModule } from '@ngrx/store';
import { EffectsModule } from '@ngrx/effects';
import { StoreDevtoolsModule } from '@ngrx/store-devtools';

import { AppComponent } from './app.component';
import { AuthlayoutComponent } from './authlayout/authlayout.component';
import { environment } from 'src/environments/environment';
import { rootReducer } from './store';

// ── Interceptors ────────────────────────────────────────────────
import { ErrorInterceptor } from './core/helpers/error.interceptor';
// (JwtInterceptor du template supprimé : il ne faisait plus rien)
/**
 * CORRIGÉ : AuthInterceptor était absent des providers
 * → aucun token JWT n'était injecté sur les requêtes vers /api/api/...
 * → toutes les requêtes après login retournaient 401 Unauthorized
 */
import { AuthInterceptor } from './core/helpers/auth.interceptor';

// ── Effects ─────────────────────────────────────────────────────
import { AuthenticationEffects } from './store/Authentication/authentication.effects';

// ── Effects — paramètres ────────────────────────────────────────
import { StatutEffects } from './store/Statut/statut.effects';
import { AgenceEffects } from './store/Agence/agence.effects';
import { DepartementEffects } from './store/Departement/departement.effects';
import { RoleEffects } from './store/Role/role.effects';
import { UserEffects } from './store/User/user.effects';
import { FonctionEffects } from './store/Fonction/fonction.effects';
import { CategoriesalarieEffects } from './store/Categoriesalarie/categoriesalarie.effects';
import { PosteEffects } from './store/Poste/poste.effects';
import { UserServiceEffects } from './store/UserService/user-service.effects';
import { UserAgenceEffects } from './store/UserAgence/user-agence.effects';
import { UserPosteEffects } from './store/UserPoste/user-poste.effects';
import { UserCategoriesalarieEffects } from './store/UserCategoriesalarie/user-categoriesalarie.effects';

// Nombres et dates au format français (1 250 000 ; 23/11/2026)
registerLocaleData(localeFr);

export function createTranslateLoader(http: HttpClient): any {
  return new TranslateHttpLoader(http, 'assets/i18n/', '.json');
}

@NgModule({
  declarations: [
    AppComponent,
    AuthlayoutComponent
  ],
  bootstrap: [AppComponent],
  imports: [
    TranslateModule.forRoot({
      defaultLanguage: 'fr',
      loader: {
        provide: TranslateLoader,
        useFactory: createTranslateLoader,
        deps: [HttpClient]
      }
    }),
    StoreModule.forRoot(rootReducer),
    StoreDevtoolsModule.instrument({
      maxAge: 25,
      logOnly: environment.production,
    }),
    EffectsModule.forRoot([
      AuthenticationEffects,
      StatutEffects,
      AgenceEffects,
      DepartementEffects,
      RoleEffects,
      UserEffects,
      FonctionEffects,
      CategoriesalarieEffects,
      PosteEffects,
      UserServiceEffects,
      UserAgenceEffects,
      UserPosteEffects,
      UserCategoriesalarieEffects
    ]),
    BrowserModule,
    BrowserAnimationsModule,
    AppRoutingModule,
    LayoutsModule,
    ToastrModule.forRoot(),
    FormsModule,
    ReactiveFormsModule,
  ],
  providers: [
    /**
     * ORDRE DES INTERCEPTEURS — critique, s'exécutent dans cet ordre
     * sur la requête sortante, en ordre inverse sur la réponse.
     *
     * 1. AuthInterceptor       → injecte le token Django JWT, refresh sur 401
     * 2. ErrorInterceptor      → extrait un message lisible des erreurs DRF
     *
     * L'intercepteur « fake backend » du template (faux utilisateurs
     * admin/123456 en localStorage) a été retiré.
     */
    { provide: LOCALE_ID, useValue: 'fr-FR' },
    { provide: HTTP_INTERCEPTORS, useClass: AuthInterceptor, multi: true },
    { provide: HTTP_INTERCEPTORS, useClass: ErrorInterceptor, multi: true },
    provideHttpClient(withInterceptorsFromDi()),
  ]
})
export class AppModule {}
