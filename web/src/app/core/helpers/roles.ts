// src/app/core/helpers/roles.ts
//
// Rôles de l'application (groupes Django) et règles d'accès côté web.
// Le backend applique les mêmes règles : ce fichier sert uniquement à
// ne pas afficher de pages / menus inaccessibles à l'utilisateur.

export type Role = 'super_admin' | 'admin' | 'gestionnaire' | 'employe';

export const ADMINS: Role[] = ['super_admin', 'admin'];
export const GESTIONNAIRES: Role[] = ['super_admin', 'admin', 'gestionnaire'];
export const EMPLOYES: Role[] = ['employe'];

/** Libellés français des rôles (affichés à la place des codes) */
export const LIBELLES_ROLES: Record<string, string> = {
  super_admin:  'Super administrateur',
  admin:        'Administrateur',
  gestionnaire: 'Gestionnaire',
  employe:      'Employé',
  admin_workflow: 'Administrateur des circuits',
  admin_finances: 'Administrateur finances',
  comptable:    'Comptable',
  direction:    'Direction',
  controleur:   'Contrôleur',
};

/** Statistiques : direction, contrôle, finances, comptabilité et administrateurs (même règle que le serveur) */
export const ROLES_STATISTIQUES = ['super_admin', 'admin', 'direction', 'controleur', 'admin_finances', 'comptable'];

/** Rôle à afficher sous le nom de l'utilisateur : le plus élevé qu'il détient */
const ORDRE_ROLES = ['super_admin', 'admin', 'admin_finances', 'admin_workflow', 'direction', 'controleur', 'comptable', 'gestionnaire', 'employe'];
export function rolePrincipal(user: any): string {
  const roles = rolesUtilisateur(user);
  const r = ORDRE_ROLES.find(x => roles.includes(x)) ?? roles[0];
  return r ? (LIBELLES_ROLES[r] ?? r) : '';
}

/** Page d'arrivée de l'utilisateur après connexion */
export function accueilUtilisateur(_user: any): string {
  return '/';
}

/** Rôles de l'utilisateur stocké après connexion (réponse de /users/me/) */
export function rolesUtilisateur(user: any): string[] {
  if (!user) return [];
  const roles: string[] = Array.isArray(user.roles) ? [...user.roles] : [];
  if (user.is_superuser && !roles.includes('super_admin')) roles.push('super_admin');
  return roles;
}

export function aUnRole(user: any, autorises?: string[] | null): boolean {
  if (!autorises || autorises.length === 0) return true;
  const roles = rolesUtilisateur(user);
  return autorises.some(r => roles.includes(r));
}

export function estGestionnaire(user: any): boolean {
  return aUnRole(user, GESTIONNAIRES);
}

/**
 * Filtre récursivement un menu : retire les entrées dont `roles` ne
 * correspond pas à l'utilisateur (ou dont `sansRoles` lui correspond), les groupes devenus vides et les
 * titres de section qui n'ont plus d'entrée.
 */
export function filtrerMenu<T extends { roles?: string[]; sansRoles?: string[]; subItems?: any; isTitle?: boolean }>(
  items: T[], user: any,
): T[] {
  const visibles = items
    .filter(item => aUnRole(user, item.roles))
    .filter(item => !item.sansRoles?.length || !aUnRole(user, item.sansRoles))
    .map(item => item.subItems
      ? { ...item, subItems: filtrerMenu(item.subItems, user) }
      : item)
    .filter(item => !item.subItems || item.subItems.length > 0);

  // Supprimer les titres suivis directement d'un autre titre (ou en fin de liste)
  return visibles.filter((item, i) =>
    !item.isTitle || (i + 1 < visibles.length && !visibles[i + 1].isTitle));
}

/**
 * Agences gérées : null pour un administrateur (toutes), sinon les agences
 * de rattachement en cours du gestionnaire (même règle que le serveur).
 */
export function agencesGerees(user: any): number[] | null {
  if (aUnRole(user, ADMINS)) return null;
  const today = new Date().toISOString().slice(0, 10);
  return (user?.user_agences ?? [])
    .filter((l: any) => String(l.date_debut).slice(0, 10) <= today
      && (!l.date_fin || String(l.date_fin).slice(0, 10) >= today))
    .map((l: any) => Number(l.agence_id ?? l.agence));
}

/** Liste d'agences réduite à celles que l'utilisateur gère */
export function filtrerAgencesGerees<T extends { id?: any }>(agences: T[], user: any): T[] {
  const gerees = agencesGerees(user);
  return gerees === null ? agences : agences.filter(a => gerees.includes(Number(a.id)));
}
