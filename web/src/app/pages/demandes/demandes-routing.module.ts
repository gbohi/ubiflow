import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { MesDemandesComponent } from './mes-demandes/mes-demandes.component';
import { NouvelleDemandeComponent } from './nouvelle-demande/nouvelle-demande.component';
import { DemandeDetailComponent } from './demande-detail/demande-detail.component';
import { AValiderComponent } from './a-valider/a-valider.component';
import { DelegationsComponent } from './delegations/delegations.component';
import { APayerComponent } from './a-payer/a-payer.component';
import { ReversementsComponent } from './reversements/reversements.component';
import { RoleGuard } from 'src/app/core/guards/role.guard';
import { ROLES_TRESORERIE } from 'src/app/core/services/tresorerie/tresorerie.service';

// Module monté à la racine des pages (voir pages-routing) : adresses /demandes, /validations, /delegations
const routes: Routes = [
  { path: 'demandes', component: MesDemandesComponent, title: 'Mes demandes | UbiFlow' },
  { path: 'demandes/nouvelle', component: NouvelleDemandeComponent, title: 'Nouvelle demande | UbiFlow' },
  { path: 'demandes/:id', component: DemandeDetailComponent, title: 'Demande | UbiFlow' },
  { path: 'validations', component: AValiderComponent, title: 'À valider | UbiFlow' },
  { path: 'delegations', component: DelegationsComponent, title: 'Délégations | UbiFlow' },
  { path: 'tresorerie/a-payer', component: APayerComponent, canActivate: [RoleGuard], data: { roles: ROLES_TRESORERIE },
    title: 'À payer | UbiFlow' },
  { path: 'tresorerie/reversements', component: ReversementsComponent, canActivate: [RoleGuard],
    data: { roles: ROLES_TRESORERIE }, title: 'Reversements | UbiFlow' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class DemandesRoutingModule {}
