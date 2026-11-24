// Formats communs des tableaux de bord.
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a'];   // palette catégorielle validée (ordre fixe)
export const BARRE = '#2a78d6';                             // barres classées : une seule teinte

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
