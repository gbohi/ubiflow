// Formats communs des tableaux de bord.
// Palette catégorielle validée (contrôle daltonisme, ordre fixe : ne jamais le permuter ni générer de teinte)
export const SERIES = ['#257de0', '#f47230', '#00b894', '#f2a600', '#ee7fac', '#008a17', '#6a4ce2', '#ec4647'];
export const BARRE = '#257de0';                             // barres classées : une seule teinte
/** Couleur fixe par groupe de statut (la couleur suit le statut, jamais son rang) */
export const COULEURS_STATUTS: Record<string, string> = {
  en_validation: '#257de0', a_corriger: '#f2a600', rejetee: '#ec4647', approuvee: '#00b894', cloturee: '#6a4ce2', annulee: '#ee7fac',
};
export const COULEURS_PAIEMENT: Record<string, string> = { paye: '#257de0', attente: '#f47230' };
/** Rampe ordinale bleue (étapes ordonnées : entonnoir), du clair au foncé */
export const RAMPE = ['#84b9f3', '#519ced', '#2370cd', '#0f4a96'];
export const ENCRE = '#191919', ENCRE2 = '#5b6470', GRILLE = '#e7e7e7', AXE = '#c2c2c2';

/** Couleurs d'une série de parts selon la palette demandée par le serveur */
export function couleursParts(palette: string | undefined, cles: string[], teintes?: (number | undefined)[]): string[] {
  if (teintes?.some(t => t !== undefined)) {
    // Rang fixe de l'entité ; la part « Autres » prend une teinte libre
    const prises = new Set(teintes.filter(t => t !== undefined));
    const libres = SERIES.map((_, i) => i).filter(i => !prises.has(i));
    return teintes.map(t => SERIES[t ?? libres.shift() ?? 0]);
  }
  if (palette === 'statuts') return cles.map((c, i) => COULEURS_STATUTS[c] ?? SERIES[i % SERIES.length]);
  if (palette === 'paiement') return cles.map((c, i) => COULEURS_PAIEMENT[c] ?? SERIES[i]);
  return cles.map((_, i) => SERIES[i]);
}

/** Styles communs des graphiques (zone, pastille de légende, bulle de survol) */
export const STYLES_GRAPHE = `.gr-zone { position: relative; }
  .gr-pastille { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 6px; vertical-align: -1px; flex: none; }
  .gr-legende { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: #5b6470; margin-bottom: 6px; }
  .gr-legende span { display: inline-flex; align-items: center; }
  .gr-bulle { position: absolute; top: 0; transform: translateX(-50%); background: #fff; border: 1px solid #e4e3df; border-radius: 8px;
    padding: 6px 10px; font-size: 12px; line-height: 1.5; box-shadow: 0 4px 12px rgba(5,37,62,.10); pointer-events: none;
    white-space: nowrap; z-index: 3; color: #191919; }
  .gr-bulle b { font-weight: 600; }`;

const insecable = (s: string) => s.replace(/[  \s]/g, ' ');

/** 1 250 000 → « 1,3 M » ; 950 000 → « 950 k » (axes, étiquettes courtes) */
export function compact(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return insecable((n / 1e9).toLocaleString('fr-FR', { maximumFractionDigits: 1 })) + ' Md';
  if (a >= 1e6) return insecable((n / 1e6).toLocaleString('fr-FR', { maximumFractionDigits: 1 })) + ' M';
  if (a >= 1e4) return insecable((n / 1e3).toLocaleString('fr-FR', { maximumFractionDigits: 0 })) + ' k';
  return insecable(n.toLocaleString('fr-FR', { maximumFractionDigits: 1 }));
}

export function complet(n: number, decimales = 0): string {
  return insecable(Number(n).toLocaleString('fr-FR', { maximumFractionDigits: decimales }));
}

/** Graduations « rondes » de 0 au maximum (4 à 5 traits) */
export function graduations(max: number): number[] {
  if (max <= 0) return [0, 1];
  const brut = max / 4;
  const p = Math.pow(10, Math.floor(Math.log10(brut)));
  const pas = [1, 2, 2.5, 5, 10].map(x => x * p).find(x => x >= brut) ?? brut;
  const t: number[] = [];
  for (let v = 0; v <= max + pas * 0.001; v += pas) t.push(v);
  if (t[t.length - 1] < max) t.push(t[t.length - 1] + pas);
  return t;
}
