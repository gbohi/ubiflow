import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

// Page route
import { DashboardsRoutingModule } from './dashboards-routing.module';
import { SharedModule } from 'src/app/shared/shared.module';

// component
import { AccueilComponent } from './accueil/accueil.component';

@NgModule({
  declarations: [
    AccueilComponent
  ],
  imports: [
    CommonModule,
    DashboardsRoutingModule,
    SharedModule,
  ]
})
export class DashboardsModule { }
