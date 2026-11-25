import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { AccueilComponent } from './accueil/accueil.component';
import { TableauxDeBordComponent } from './tableaux-de-bord/tableaux-de-bord.component';
import { StatistiquesComponent } from './statistiques/statistiques.component';
import { RoleGuard } from 'src/app/core/guards/role.guard';
import { ROLES_STATISTIQUES } from 'src/app/core/helpers/roles';


const routes: Routes = [
  { path: '', pathMatch: 'full', component: AccueilComponent, title: 'Accueil | UbiFlow' },
  { path: 'tableaux-de-bord', component: TableauxDeBordComponent, title: 'Tableaux de bord | UbiFlow' },
  { path: 'statistiques', component: StatistiquesComponent, canActivate: [RoleGuard], data: { roles: ROLES_STATISTIQUES },
    title: 'Statistiques | UbiFlow' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class DashboardsRoutingModule { }
