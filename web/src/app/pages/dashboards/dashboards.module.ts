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
import { GrapheCourbeComponent } from './graphes/graphe-courbe.component';
import { GrapheAnneauComponent } from './graphes/graphe-anneau.component';
import { GrapheEmpileComponent } from './graphes/graphe-empile.component';
import { GrapheEntonnoirComponent } from './graphes/graphe-entonnoir.component';
import { GrapheCarteComponent } from './graphes/graphe-carte.component';
import { StatistiquesComponent } from './statistiques/statistiques.component';

@NgModule({
  declarations: [
    AccueilComponent, TableauxDeBordComponent, GrapheBarresComponent, GrapheColonnesComponent,
    GrapheCourbeComponent, GrapheAnneauComponent, GrapheEmpileComponent, GrapheEntonnoirComponent, GrapheCarteComponent,
    StatistiquesComponent,
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
