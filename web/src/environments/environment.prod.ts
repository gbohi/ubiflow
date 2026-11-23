// src/environments/environment.prod.ts
export const environment = {
  production: true,

  // Vide = même serveur que le site : en production, Nginx sert le site
  // Angular ET l'API (/api/...). Le site fonctionne donc quelle que soit
  // l'adresse du serveur (IP, nom de domaine, HTTP ou HTTPS).
  apiUrl: ''
};
