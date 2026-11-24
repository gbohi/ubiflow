// src/app/pages/parametres/categoriesalarie/categoriesalarie.component.ts

import { Component, OnInit, AfterViewInit, ViewChild, ElementRef, DestroyRef, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DecimalPipe, DatePipe } from '@angular/common';
import { UntypedFormBuilder, UntypedFormGroup, Validators } from '@angular/forms';
import { ToastrService } from 'ngx-toastr';
import { ModalDirective } from 'ngx-bootstrap/modal';
import { Store } from '@ngrx/store';
import { Actions, ofType } from '@ngrx/effects';
import { PageChangedEvent } from 'ngx-bootstrap/pagination';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, map } from 'rxjs/operators';

import {
  addcategoriesalarieData,
  addcategoriesalarieDataSuccess,
  addcategoriesalarieDataFailure,
  deletecategoriesalarieData,
  deletecategoriesalarieSuccess,
  deletecategoriesalarieFailure,
  deletemultiplecategoriesalarieData,
  deletemultiplecategoriesalarieSuccess,
  deletemultiplecategoriesalarieFailure,
  fetchcategoriesalarieData,
  updatecategoriesalarieData,
  updatecategoriesalarieDataSuccess,
  updatecategoriesalarieDataFailure,
} from 'src/app/store/Categoriesalarie/categoriesalarie.action';
import {
  selectcategoriesalarieData,
  selectTotalItems,
  selectLoading,
  selectCurrentPage,
} from 'src/app/store/Categoriesalarie/categoriesalarie-selector';
import { TriServeur } from 'src/app/shared/tri-serveur';
import { ColonneExport } from 'src/app/shared/export-liste/export-liste.component';

@Component({
  selector: 'app-categoriesalarie',
  templateUrl: './categoriesalarie.component.html',
  styleUrl: './categoriesalarie.component.scss',
  providers: [DecimalPipe, DatePipe],
})
export class CategoriesalarieComponent implements OnInit, AfterViewInit {
  // ── Export Excel / PDF (toutes les lignes filtrées) ──
  readonly colonnesExport: ColonneExport[] = [{ libelle: 'Libellé', champ: 'libelle' }];
  get paramsExport(): Record<string, any> { return { search: this.searchTerm, ordering: this.tri.ordering }; }


  // Tri serveur des colonnes : clé de colonne → champ autorisé par l'API (ordering_fields)
  readonly tri = new TriServeur({ id: 'id', libelle: 'libelle' });

  private destroyRef = inject(DestroyRef);
  private actions$   = inject(Actions);

  breadCrumbItems = [
    { label: 'Paramètres', active: false },
    { label: 'Catégories de salarié', active: true },
  ];

  categoriesalaries:    any[] = [];
  totalItems  = 0;
  currentPage = 1;
  isLoading   = true;

  categoriesalarieForm!: UntypedFormGroup;
  submitted      = false;
  isEdit         = false;
  saving         = false;
  deleting       = false;
  masterSelected = false;
  term: any;
  checkedValGet: any[] = [];
  selectedCategoriesalarie: any   = null;
  deleteID: any;
  direction = 'asc';

  /** Terme de recherche effectivement envoyé au serveur (?search=) */
  private searchTerm = '';
  private search$    = new Subject<string>();

  private lastActiveElement: HTMLElement | null = null;

  @ViewChild('addCategoriesalarie',           { static: false }) addCategoriesalarie?:           ModalDirective;
  @ViewChild('deleteRecordModal', { static: false }) deleteRecordModal?: ModalDirective;
  @ViewChild('viewCategoriesalarie',          { static: false }) viewCategoriesalarie?:          ModalDirective;
  @ViewChild('mainContainer',     { static: false }) mainContainer?:     ElementRef;

  constructor(
    private fb: UntypedFormBuilder,
    private toastService: ToastrService,
    private store: Store,
  ) {}

  ngOnInit(): void {
    this.categoriesalarieForm = this.fb.group({
      id:           [''],
      libelle: ['', [Validators.required]],
    });

    this.store.select(selectLoading).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(loading => {
      this.isLoading = loading;
    });

    this.store.select(selectTotalItems).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(total => {
      this.totalItems = total ?? 0;
    });

    this.store.select(selectCurrentPage).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(page => {
      this.currentPage = page ?? 1;
    });

    this.store.select(selectcategoriesalarieData).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(data => {
      if (data) {
        this.categoriesalaries = data.map(item => ({ ...item, state: false }));
        this.resetSelection();
      }
    });

    // ── Recherche serveur (debounce 300 ms, retour page 1) ──
    this.search$.pipe(
      map(t => (t ?? '').toString().trim()),
      debounceTime(300),
      distinctUntilChanged(),
      takeUntilDestroyed(this.destroyRef),
    ).subscribe(t => {
      this.searchTerm = t;
      this.loadData(1);
    });

    // ── Réponses du serveur (ajout / modification) ─────────
    this.actions$.pipe(ofType(addcategoriesalarieDataSuccess, updatecategoriesalarieDataSuccess), takeUntilDestroyed(this.destroyRef))
      .subscribe(action => {
        this.saving    = false;
        this.submitted = false;
        this.toastService.success(
          action.type === addcategoriesalarieDataSuccess.type ? 'Catégorie de salarié ajoutée avec succès !' : 'Catégorie de salarié mise à jour avec succès !',
          'Succès'
        );
        this.closeAddModal();
      });

    this.actions$.pipe(ofType(addcategoriesalarieDataFailure, updatecategoriesalarieDataFailure), takeUntilDestroyed(this.destroyRef))
      .subscribe(({ error }) => {
        // La modale reste ouverte avec les valeurs saisies
        this.saving = false;
        this.toastService.error(error || 'Enregistrement impossible.', 'Erreur');
      });

    // ── Réponses du serveur (suppression) ──────────────────
    this.actions$.pipe(ofType(deletecategoriesalarieSuccess, deletemultiplecategoriesalarieSuccess), takeUntilDestroyed(this.destroyRef))
      .subscribe(action => {
        this.toastService.success(
          action.type === deletecategoriesalarieSuccess.type ? 'Catégorie de salarié supprimée avec succès !' : 'Catégories de salarié supprimées avec succès !',
          'Succès'
        );
        this.afterDeleteActions();
      });

    this.actions$.pipe(ofType(deletecategoriesalarieFailure, deletemultiplecategoriesalarieFailure), takeUntilDestroyed(this.destroyRef))
      .subscribe(({ error }) => {
        // La ligne reste affichée : on montre seulement l'erreur
        this.deleting = false;
        this.toastService.error(error || 'Suppression impossible.', 'Erreur');
        this.closeDeleteModal();
      });

    this.loadData(1);
  }

  ngAfterViewInit(): void {
    this.addCategoriesalarie?.onHidden.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.categoriesalarieForm.reset();
      this.submitted = false;
      this.saving    = false;
      this.isEdit    = false;
    });

    this.deleteRecordModal?.onHidden.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      this.deleteID = null;
      this.deleting = false;
    });
  }

  // ── Chargement ────────────────────────────────────────────
  loadData(page: number = 1): void {
    this.store.dispatch(fetchcategoriesalarieData({ page, search: this.searchTerm || undefined, ordering: this.tri.ordering }));
  }

  private resetSelection(): void {
    this.checkedValGet  = [];
    this.masterSelected = false;
  }

  // ── Modal Ajouter ─────────────────────────────────────────
  openAddModal(): void {
    this.lastActiveElement = document.activeElement as HTMLElement;
    this.categoriesalarieForm.reset();
    this.submitted = false;
    this.isEdit    = false;
    this.addCategoriesalarie?.show();
  }

  closeAddModal(): void {
    this.lastActiveElement?.focus();
    setTimeout(() => this.addCategoriesalarie?.hide(), 10);
  }

  // ── Modal Édition ─────────────────────────────────────────
  editList(id: any): void {
    this.lastActiveElement = document.activeElement as HTMLElement;
    const editData = this.categoriesalaries.find(p => p.id === id);
    if (!editData) return;

    this.categoriesalarieForm.reset();
    this.categoriesalarieForm.patchValue(editData);
    this.submitted = false;
    this.isEdit    = true;
    this.addCategoriesalarie?.show();
  }

  // ── Sauvegarde (ajout / mise à jour) ─────────────────────
  saveProperty(): void {
    this.submitted = true;
    if (this.categoriesalarieForm.invalid) {
      this.toastService.error('Veuillez vérifier les informations saisies.', 'Erreur');
      return;
    }
    if (this.saving) return;

    const formValue = { ...this.categoriesalarieForm.value };
    this.saving = true;

    if (formValue.id) {
      this.store.dispatch(updatecategoriesalarieData({ updatedData: formValue }));
    } else {
      delete formValue.id;
      this.store.dispatch(addcategoriesalarieData({ newData: formValue }));
    }
    // Toast + fermeture de la modale à la réponse du serveur (voir ngOnInit)
  }

  // ── Modal Suppression ─────────────────────────────────────
  removeItem(id: any): void {
    this.lastActiveElement = document.activeElement as HTMLElement;
    this.deleteID = id;
    this.deleteRecordModal?.show();
  }

  openBulkDelete(): void {
    this.lastActiveElement = document.activeElement as HTMLElement;
    this.deleteID = null;
    this.deleteRecordModal?.show();
  }

  closeDeleteModal(): void {
    this.lastActiveElement?.focus();
    setTimeout(() => this.deleteRecordModal?.hide(), 10);
  }

  get deleteMessage(): string {
    if (this.deleteID) {
      const libelle = this.categoriesalaries.find(e => e.id === this.deleteID)?.libelle;
      return libelle ? `la catégorie de salarié « ${libelle} »` : 'cette catégorie de salarié';
    }
    const n = this.checkedValGet.length;
    return n > 1 ? `ces ${n} catégories de salarié` : 'cette catégorie de salarié';
  }

  confirmDelete(id?: any): void {
    if (this.deleting) return;

    if (id) {
      this.deleting = true;
      this.store.dispatch(deletecategoriesalarieData({ id: id.toString() }));
      return;
    }

    if (this.checkedValGet?.length > 0) {
      this.deleting = true;
      this.store.dispatch(deletemultiplecategoriesalarieData({ id: this.checkedValGet.join(',') }));
      return;
    }

    this.toastService.error('Aucune catégorie de salarié sélectionnée.', 'Erreur');
    this.closeDeleteModal();
  }

  private afterDeleteActions(): void {
    this.closeDeleteModal();
    this.deleting = false;
    this.deleteID = null;
    this.resetSelection();
  }

  // ── Modal Détails ─────────────────────────────────────────
  viewDetails(id: any): void {
    this.lastActiveElement = document.activeElement as HTMLElement;
    const categoriesalarieData = this.categoriesalaries.find(p => p.id === id);
    if (categoriesalarieData) {
      this.selectedCategoriesalarie = categoriesalarieData;
      this.viewCategoriesalarie?.show();
    } else {
      this.toastService.error('Catégorie de salarié introuvable', 'Erreur');
    }
  }

  closeViewModal(): void {
    this.lastActiveElement?.focus();
    setTimeout(() => {
      this.viewCategoriesalarie?.hide();
      this.selectedCategoriesalarie = null;
    }, 10);
  }

  // ── Checkboxes ────────────────────────────────────────────
  checkUncheckAll(ev: any): void {
    this.categoriesalaries.forEach(x => x.state = ev.target.checked);
    this.masterSelected = ev.target.checked;
    this.updateCheckedValues();
  }

  onCheckboxChange(): void {
    this.updateCheckedValues();
  }

  private updateCheckedValues(): void {
    this.checkedValGet = this.categoriesalaries
      .filter(e => e.state === true)
      .map(e => e.id);
    this.masterSelected = this.categoriesalaries.length > 0 && this.checkedValGet.length === this.categoriesalaries.length;
  }

  // Tri côté serveur (?ordering=) : s'applique à toutes les données, pas seulement à la page affichée.
  // Un nouveau clic inverse le sens ; la recherche courante est conservée et on revient à la page 1.
  onSort(column: string): void {
    if (this.tri.basculer(column)) this.loadData(1);
  }

  // ── Recherche (côté serveur) ──────────────────────────────
  filterdata(value?: string): void {
    this.search$.next(value ?? this.term ?? '');
  }

  // ── Pagination (le terme de recherche est conservé) ───────
  pageChanged(event: PageChangedEvent): void {
    this.loadData(event.page);
  }
}
