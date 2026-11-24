import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NgSelectModule } from '@ng-select/ng-select';

// Page route
import { DashboardsRoutingModule } from './dashboards-routing.module';
import { SharedModule } from 'src/app/shared/shared.module';

// component
import { AccueilComponent } from './accueil/accueil.component';
import { TableauxDeBordComponent } from './tableaux-de-bord/tableaux-de-bord.component';
import { GrapheBarresComponent } from './graphes/graphe-barres.component';
import { GrapheColonnesComponent } from './graphes/graphe-colonnes.component';

@NgModule({
  declarations: [
    AccueilComponent, TableauxDeBordComponent, GrapheBarresComponent, GrapheColonnesComponent,
  ],
  imports: [
    CommonModule,
    DashboardsRoutingModule,
    SharedModule,
    FormsModule,
    NgSelectModule,
  ]
})
export class DashboardsModule { }
