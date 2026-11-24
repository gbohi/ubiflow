import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AccueilComponent } from './accueil/accueil.component';
import { TableauxDeBordComponent } from './tableaux-de-bord/tableaux-de-bord.component';


const routes: Routes = [
  { path: '', pathMatch: 'full', component: AccueilComponent, title: 'Accueil | UbiFlow' },
  { path: 'tableaux-de-bord', component: TableauxDeBordComponent, title: 'Tableaux de bord | UbiFlow' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class DashboardsRoutingModule { }
