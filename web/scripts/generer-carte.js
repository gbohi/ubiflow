// Génère src/assets/geo/carte.json : fonds de carte pré-projetés (chemins SVG) pour la page Statistiques.
// Données : Natural Earth (domaine public) via world-atlas. À relancer seulement pour changer le fond :
//   npm i --no-save world-atlas@2 topojson-client@3 i18n-iso-countries@7 && node scripts/generer-carte.js
const fs = require('fs');
const path = require('path');
const topojson = require('topojson-client');
const pays = require('i18n-iso-countries');

function chemins(features, proj) {
  const r = n => Math.round(n * 10) / 10;
  return features.map(f => {
    const g = f.geometry; if (!g) return null;
    const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
    const d = polys.map(p => p.map(anneau => {
      // Anneau à cheval sur l'antiméridien (Russie, Fidji) : longitudes déroulées, la partie hors cadre est masquée
      const saute = anneau.some((pt, i) => i && Math.abs(pt[0] - anneau[i - 1][0]) > 180);
      const pts = anneau.map(([lon, lat]) => proj(saute && lon < 0 ? lon + 360 : lon, lat));
      return 'M' + pts.map(([x, y]) => `${r(x)},${r(y)}`).join('L') + 'Z';
    }).join('')).join('');
    return { iso: pays.numericToAlpha2(String(f.id).padStart(3, '0')) || '', d };
  }).filter(Boolean);
}

const base = path.dirname(require.resolve('world-atlas/package.json'));
const t50 = JSON.parse(fs.readFileSync(path.join(base, 'countries-50m.json')));
const t110 = JSON.parse(fs.readFileSync(path.join(base, 'countries-110m.json')));

// Côte d'Ivoire et voisins : équirectangulaire corrigée à la latitude moyenne
const ci = { lonMin: -9.0, lonMax: -2.2, latMin: 4.1, latMax: 11.0 };
const cosLat = Math.cos((7.5 * Math.PI) / 180), kCi = 600 / ((ci.lonMax - ci.lonMin) * cosLat);
const projCi = (lon, lat) => [(lon - ci.lonMin) * cosLat * kCi, (ci.latMax - lat) * kCi];
const voisins = ['CI', 'LR', 'GN', 'ML', 'BF', 'GH'];
const f50 = topojson.feature(t50, t50.objects.countries).features
  .filter(f => voisins.includes(pays.numericToAlpha2(String(f.id).padStart(3, '0'))));

// Monde (sans l'Antarctique)
const monde = { lonMin: -180, lonMax: 180, latMin: -56, latMax: 84 }, kM = 1000 / 360;
const projM = (lon, lat) => [(lon - monde.lonMin) * kM, (monde.latMax - lat) * kM];
const f110 = topojson.feature(t110, t110.objects.countries).features.filter(f => String(f.id) !== '010');

const sortie = {
  source: 'Natural Earth (domaine public), via world-atlas',
  ci: { ...ci, cosLat, k: kCi, largeur: 600, hauteur: Math.round((ci.latMax - ci.latMin) * kCi), pays: chemins(f50, projCi) },
  monde: { ...monde, k: kM, largeur: 1000, hauteur: Math.round((monde.latMax - monde.latMin) * kM), pays: chemins(f110, projM) },
};
fs.writeFileSync(path.join(__dirname, '../src/assets/geo/carte.json'), JSON.stringify(sortie));
console.log('carte.json :', Math.round(JSON.stringify(sortie).length / 1024), 'ko');
