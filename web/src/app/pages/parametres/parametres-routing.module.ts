import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { RoleGuard } from 'src/app/core/guards/role.guard';
import { ADMINS, GESTIONNAIRES } from 'src/app/core/helpers/roles';

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
import { TypesDemandeComponent } from './types-demande/types-demande.component';
import { WorkflowsComponent } from './workflows/workflows.component';
import { WorkflowEditeurComponent } from './workflow-editeur/workflow-editeur.component';
import { JournalComponent } from './journal/journal.component';
import { BaremesComponent } from './baremes/baremes.component';
import { LieuxComponent } from './lieux/lieux.component';
import { SocieteComponent } from './societe/societe.component';
import { CalendrierComponent } from './calendrier/calendrier.component';
import { PerimetresComponent } from './perimetres/perimetres.component';

const ADMIN_WORKFLOW = ['super_admin', 'admin', 'admin_workflow'];
const FINANCES = ['super_admin', 'admin', 'admin_finances', 'comptable', 'controleur'];


const routes: Routes = [
  // Accueil des paramètres : cartes par thème, filtrées selon les routes ci-dessous
  { path: '', pathMatch: 'full', redirectTo: 'accueil' },
  { path: 'accueil', component: AccueilParametresComponent, canActivate: [RoleGuard], data: { roles: GESTIONNAIRES } },
  // Les « services » (modèle Service de l'API) sont gérés par la page Départements
  { path: 'service', redirectTo: 'departement' },
  { path: 'user', component: UserComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'role', component: RoleComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'statut', component: StatutComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'agence', component: AgenceComponent, canActivate: [RoleGuard], data: { roles: GESTIONNAIRES } },
  { path: 'departement', component: DepartementComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'poste', component: PosteComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'fonction', component: FonctionComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'categorie-salarie', component: CategoriesalarieComponent, canActivate: [RoleGuard], data: { roles: ADMINS } },
  { path: 'responsabilite', component: ResponsabiliteComponent, canActivate: [RoleGuard], data: { roles: ADMINS },
    title: 'Responsabilités | UbiFlow' },
  { path: 'organigramme', component: OrganigrammeComponent, canActivate: [RoleGuard], data: { roles: GESTIONNAIRES },
    title: 'Organigramme | UbiFlow' },
  { path: 'types-demande', component: TypesDemandeComponent, canActivate: [RoleGuard], data: { roles: ADMIN_WORKFLOW },
    title: 'Types de demande | UbiFlow' },
  { path: 'workflows', component: WorkflowsComponent, canActivate: [RoleGuard], data: { roles: ADMIN_WORKFLOW },
    title: 'Circuits de validation | UbiFlow' },
  { path: 'workflows/:id', component: WorkflowEditeurComponent, canActivate: [RoleGuard], data: { roles: ADMIN_WORKFLOW },
    title: 'Circuit de validation | UbiFlow' },
  { path: 'journal', component: JournalComponent, canActivate: [RoleGuard], data: { roles: ['super_admin', 'admin', 'controleur'] },
    title: "Journal d'activité | UbiFlow" },
  { path: 'baremes', component: BaremesComponent, canActivate: [RoleGuard], data: { roles: FINANCES },
    title: 'Barèmes | UbiFlow' },
  { path: 'lieux', component: LieuxComponent, canActivate: [RoleGuard], data: { roles: FINANCES },
    title: 'Lieux et distances | UbiFlow' },
  { path: 'perimetres', component: PerimetresComponent, canActivate: [RoleGuard], data: { roles: ADMINS },
    title: 'Périmètres de consultation | UbiFlow' },
  { path: 'calendrier', component: CalendrierComponent, canActivate: [RoleGuard], data: { roles: ADMINS },
    title: 'Calendrier | UbiFlow' },
  { path: 'societe', component: SocieteComponent, canActivate: [RoleGuard], data: { roles: ['super_admin', 'admin', 'admin_finances'] },
    title: 'Société | UbiFlow' },
  { path: 'import-collaborateurs', component: ImportCollaborateursComponent, canActivate: [RoleGuard], data: { roles: ADMINS },
    title: 'Import des collaborateurs | UbiFlow' },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class ParametresRoutingModule { }
