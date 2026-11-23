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
import { ResponsabiliteComponent } from './responsabilite/responsabilite.component';
import { OrganigrammeComponent } from './organigramme/organigramme.component';
import { ImportCollaborateursComponent } from './import-collaborateurs/import-collaborateurs.component';
import { OrganisationCollaborateurComponent } from './user/organisation-collaborateur/organisation-collaborateur.component';
import { NgSelectModule } from '@ng-select/ng-select';
import { TypesDemandeComponent } from './types-demande/types-demande.component';
import { WorkflowsComponent } from './workflows/workflows.component';
import { WorkflowEditeurComponent } from './workflow-editeur/workflow-editeur.component';
import { JournalComponent } from './journal/journal.component';

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
    ResponsabiliteComponent,
    OrganigrammeComponent,
    ImportCollaborateursComponent,
    OrganisationCollaborateurComponent,
    TypesDemandeComponent,
    WorkflowsComponent,
    WorkflowEditeurComponent,
    JournalComponent,
  ],
  imports: [
    CommonModule,
    SharedModule,
    PaginationModule.forRoot(),
    FormsModule,
    ReactiveFormsModule,
    ParametresRoutingModule,
    ModalModule.forRoot(),
    NgSelectModule,
  ],
  providers: [
    DatePipe
  ],

})
export class ParametresModule { }
