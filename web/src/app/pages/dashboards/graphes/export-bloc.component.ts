// Bouton « Exporter » d'un seul graphique ou d'une seule liste : Excel (valeurs) ou PDF (graphique et valeurs).
import { Component, EventEmitter, Input, Output } from '@angular/core';

@Component({
  selector: 'app-export-bloc',
  template: `
    <div class="btn-group" dropdown placement="bottom right" container="body">
      <button type="button" class="btn btn-link btn-sm p-0 text-nowrap" dropdownToggle [disabled]="desactive"
              [attr.aria-label]="'Exporter ce bloc'" title="Exporter ce bloc">
        <i class="ri-download-2-line me-1"></i>Exporter</button>
      <ul *dropdownMenu class="dropdown-menu dropdown-menu-end" role="menu">
        <li><button type="button" class="dropdown-item" (click)="excel.emit()"><i class="ri-file-excel-2-line me-2 text-success"></i>Excel</button></li>
        <li><button type="button" class="dropdown-item" (click)="pdf.emit()"><i class="ri-file-pdf-2-line me-2 text-danger"></i>PDF</button></li>
      </ul>
    </div>`,
})
export class ExportBlocComponent {
  @Input() desactive = false;
  @Output() excel = new EventEmitter<void>();
  @Output() pdf = new EventEmitter<void>();
}
