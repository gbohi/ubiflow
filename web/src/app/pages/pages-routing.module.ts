import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  {
    // Demandes, validations, délégations (adresses /demandes, /validations, /delegations)
    path: '', loadChildren: () => import('./demandes/demandes.module').then(m => m.DemandesModule)
  },
  {
    path: '', loadChildren: () => import('./dashboards/dashboards.module').then(m => m.DashboardsModule)
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
