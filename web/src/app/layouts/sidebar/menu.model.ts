export interface MenuItem {
    id?: number;
    label?: any;
    icon?: string;
    link?: string;
    subItems?: any;
    isTitle?: boolean;
    badge?: any;
    parentId?: number;
    isLayout?: boolean;
    isOpen?: boolean;
    /** Rôles autorisés à voir l'entrée (aucun = tout utilisateur connecté) */
    roles?: string[];
    /** Rôles pour lesquels l'entrée est masquée (ex. « Accueil » employé caché aux gestionnaires) */
    sansRoles?: string[];
    /** Autres adresses (préfixes) pour lesquelles l'entrée est affichée comme active */
    actifSur?: string[];
    /**
     * Pastille « Nouveau » à côté du libellé, jusqu'à cette date (AAAA-MM-JJ)
     * incluse et tant que l'utilisateur n'a pas ouvert la page (sidebar).
     */
    isNew?: boolean | string;
}