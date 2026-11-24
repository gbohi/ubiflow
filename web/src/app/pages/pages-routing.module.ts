import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  {
    // Accueil (/) et tableaux de bord : en premier, sinon l'adresse vide reste sans page
    path: '', loadChildren: () => import('./dashboards/dashboards.module').then(m => m.DashboardsModule)
  },
  {
    // Demandes, validations, délégations, trésorerie (adresses /demandes, /validations, /delegations…)
    path: '', loadChildren: () => import('./demandes/demandes.module').then(m => m.DemandesModule)
  },
  {
    // Rôle vérifié route par route dans ParametresRoutingModule
    path: 'parametres', loadChildren: () => import('./parametres/parametres.module').then(m => m.ParametresModule)
  },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class PagesRoutingModule { }
