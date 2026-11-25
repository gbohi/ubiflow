// Rendu d'un graphique SVG en image PNG (exports PDF des tableaux de bord et des statistiques)
export function svgVersPng(svg: SVGSVGElement): Promise<string> {
  return new Promise((resolve, reject) => {
    const vb = svg.viewBox.baseVal;
    const copie = svg.cloneNode(true) as SVGSVGElement;
    copie.setAttribute('width', String(vb.width));
    copie.setAttribute('height', String(vb.height));
    const texte = new XMLSerializer().serializeToString(copie);
    const img = new Image();
    img.onload = () => {
      const c = document.createElement('canvas');
      c.width = vb.width * 2; c.height = vb.height * 2;
      const ctx = c.getContext('2d');
      if (!ctx) { reject(new Error('Canvas indisponible')); return; }
      ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, c.width, c.height); ctx.scale(2, 2); ctx.drawImage(img, 0, 0);
      resolve(c.toDataURL('image/png'));
    };
    img.onerror = () => reject(new Error('Rendu du graphique impossible'));
    img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(texte);
  });
}
