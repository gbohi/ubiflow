// src/app/layouts/cloche-notifications/cloche-notifications.component.ts
//
// Cloche de la barre du haut : nombre de notifications non lues (rafraîchi
// chaque minute), dernières notifications, ouverture de la demande concernée.

import { Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Router } from '@angular/router';
import { timer } from 'rxjs';
import { switchMap } from 'rxjs/operators';
import { DemandesService, Notification } from 'src/app/core/services/demandes/demandes.service';

@Component({
  selector: 'app-cloche-notifications',
  template: `
    <div dropdown class="dropdown topbar-head-dropdown ms-1 header-item" (onShown)="charger()">
      <button dropdownToggle type="button" class="btn btn-icon btn-topbar btn-ghost-dark rounded-circle position-relative"
              aria-label="Notifications">
        <i class="ri-notification-3-line fs-2xl"></i>
        @if (nonLues > 0) {
          <span class="position-absolute topbar-badge translate-middle badge rounded-pill bg-danger" style="top: 8px; left: 75%; font-size: .65rem">
            {{ nonLues > 99 ? '99+' : nonLues }}</span>
        }
      </button>
      <div *dropdownMenu class="dropdown-menu dropdown-menu-lg dropdown-menu-end p-0">
        <div class="d-flex align-items-center p-3 border-bottom">
          <h6 class="m-0 fs-base">Notifications</h6>
          @if (nonLues > 0) { <button type="button" class="btn btn-link btn-sm ms-auto p-0" (click)="toutLire($event)">Tout marquer comme lu</button> }
        </div>
        <div style="max-height: 360px; overflow: auto">
          @for (n of notifications; track n.id) {
            <a href="javascript:void(0)" class="dropdown-item py-2 border-bottom" [class.bg-light]="!n.lue" (click)="ouvrir(n)" style="white-space: normal">
              <div class="d-flex gap-2">
                <i class="ri-notification-badge-line mt-1" [class.text-primary]="!n.lue" [class.text-muted]="n.lue"></i>
                <div><div class="small" [class.fw-semibold]="!n.lue">{{ n.titre }}</div>
                  <div class="small text-muted">{{ n.message }}</div>
                  <div class="text-muted" style="font-size: .7rem">{{ n.creee_le | date:'dd/MM/yyyy HH:mm' }}</div></div>
              </div>
            </a>
          } @empty {
            <div class="p-3 text-center text-muted small">Aucune notification.</div>
          }
        </div>
      </div>
    </div>
  `,
})
export class ClocheNotificationsComponent implements OnInit {
  private readonly service = inject(DemandesService);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);

  nonLues = 0;
  notifications: Notification[] = [];

  ngOnInit(): void {
    timer(0, 60000).pipe(switchMap(() => this.service.compteurNotifications()), takeUntilDestroyed(this.destroyRef))
      .subscribe({ next: r => this.nonLues = r.non_lues, error: () => {} });
  }

  charger(): void {
    this.service.notifications().subscribe(n => this.notifications = n.slice(0, 15));
  }

  ouvrir(n: Notification): void {
    if (!n.lue) {
      this.service.lireNotification(n.id).subscribe();
      n.lue = true;
      this.nonLues = Math.max(0, this.nonLues - 1);
    }
    if (n.lien) this.router.navigateByUrl(n.lien);
  }

  toutLire(evt: Event): void {
    evt.stopPropagation();
    this.service.toutLire().subscribe(() => {
      this.nonLues = 0;
      this.notifications.forEach(n => n.lue = true);
    });
  }
}
