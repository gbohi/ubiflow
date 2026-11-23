// src/app/shared/montant.pipe.ts
import { Pipe, PipeTransform } from '@angular/core';

/**
 * Montant au format français avec une espace insécable classique entre les
 * milliers (l'espace fine du format Angular « fr » n'est pas dessinée par la
 * police Poppins : « 1500 000 »).
 *   {{ demande.montant_demande | montant:demande.devise }}  →  1 500 000 XOF
 */
@Pipe({ name: 'montant' })
export class MontantPipe implements PipeTransform {
  transform(valeur: string | number | null | undefined, devise = '', decimales = 2): string {
    if (valeur === null || valeur === undefined || valeur === '') return '—';
    const n = Number(valeur);
    if (Number.isNaN(n)) return String(valeur);
    const texte = n.toLocaleString('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: decimales })
      .replace(/[  \s]/g, ' ');
    return devise ? `${texte} ${devise}` : texte;
  }
}
