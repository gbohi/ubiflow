import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RoleGuard } from 'src/app/core/guards/role.guard';
import { ADMINS, GESTIONNAIRES } from 'src/app/core/helpers/roles';

import { AccueilParametresComponent } from './accueil-parametres/accueil-parametres.component';
import { AgenceComponent } from './agence/agence.component';
import { StatutComponent } from './statut/statut.component';
import { DepartementComponent } from './departement/departement.component';
import { RoleComponent } from './role/role.component';
import { UserComponent } from './user/user.component';
import { FonctionComponent } from './fonction/fonction.component';
import { CategoriesalarieComponent } from './categoriesalarie/categoriesalarie.component';
import { PosteComponent } from './poste/poste.component';


const routes: Routes = [
  // Accueil des paramètres : cartes par thème, filtrées selon les routes ci-dessous
  { path: '', pathMatch: 'full', redirectTo: 'accueil' },
  { path: 'accueil', component: AccueilParametresComponent, canActivate: [RoleGuard], data: { roles: GESTIONNAIRES } },
  // Les « services » (modèle Service de l'API) sont gérés par la page Départements
  { path: 'service', redirectTo: 'departement' },
  { path: 'user', component: UserComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'role', component: RoleComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'statut', component: StatutComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'agence', component: AgenceComponent, canActivate: [RoleGuard], data: { roles: GESTIONNAIRES } },
  { path: 'departement', component: DepartementComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'poste', component: PosteComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'fonction', component: FonctionComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'categorie-salarie', component: CategoriesalarieComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ParametresRoutingModule { }
