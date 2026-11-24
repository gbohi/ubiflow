import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ModalModule } from 'ngx-bootstrap/modal';
import { NgSelectModule } from '@ng-select/ng-select';
import { SharedModule } from 'src/app/shared/shared.module';

import { DemandesRoutingModule } from './demandes-routing.module';
import { ChampsDemandeComponent } from './champs-demande/champs-demande.component';
import { MesDemandesComponent } from './mes-demandes/mes-demandes.component';
import { NouvelleDemandeComponent } from './nouvelle-demande/nouvelle-demande.component';
import { DemandeDetailComponent } from './demande-detail/demande-detail.component';
import { AValiderComponent } from './a-valider/a-valider.component';
import { DelegationsComponent } from './delegations/delegations.component';
import { MissionFormComponent } from './mission-form/mission-form.component';
import { RecapMissionComponent } from './recap-mission/recap-mission.component';
import { PaiementModalComponent } from './paiement-modal/paiement-modal.component';
import { APayerComponent } from './a-payer/a-payer.component';
import { ReversementsComponent } from './reversements/reversements.component';

@NgModule({
  declarations: [
    ChampsDemandeComponent, MesDemandesComponent, NouvelleDemandeComponent, DemandeDetailComponent,
    AValiderComponent, DelegationsComponent, MissionFormComponent, RecapMissionComponent,
    PaiementModalComponent, APayerComponent, ReversementsComponent,
  ],
  imports: [CommonModule, FormsModule, SharedModule, ModalModule.forRoot(), NgSelectModule, DemandesRoutingModule],
  exports: [ChampsDemandeComponent],
})
export class DemandesModule {}
