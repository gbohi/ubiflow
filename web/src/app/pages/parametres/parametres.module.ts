import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

// Page route
import { ParametresRoutingModule } from './parametres-routing.module';
import { SharedModule } from 'src/app/shared/shared.module';

// Date Format
import { DatePipe } from '@angular/common';

// bootstrap component
import { PaginationModule } from 'ngx-bootstrap/pagination';
import { ModalModule } from 'ngx-bootstrap/modal';

// component
import { AccueilParametresComponent } from './accueil-parametres/accueil-parametres.component';
import { AgenceComponent } from './agence/agence.component';
import { StatutComponent } from './statut/statut.component';
import { DepartementComponent } from './departement/departement.component';
import { RoleComponent } from './role/role.component';
import { UserComponent } from './user/user.component';
import { FonctionComponent } from './fonction/fonction.component';
import { CategoriesalarieComponent } from './categoriesalarie/categoriesalarie.component';
import { PosteComponent } from './poste/poste.component';

@NgModule({
  declarations: [
    AccueilParametresComponent,
    AgenceComponent,
    StatutComponent,
    DepartementComponent,
    RoleComponent,
    UserComponent,
    FonctionComponent,
    CategoriesalarieComponent,
    PosteComponent,
  ],
  imports: [
    CommonModule,
    SharedModule,
    PaginationModule.forRoot(),
    FormsModule,
    ReactiveFormsModule,
    ParametresRoutingModule,
    ModalModule.forRoot(),
  ],
  providers: [
    DatePipe
  ],

})
export class ParametresModule { }
