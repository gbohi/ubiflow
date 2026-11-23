import { MenuItem } from "./menu.model";

import { GESTIONNAIRES } from "../../core/helpers/roles";


export const MENU: MenuItem[] = [
    {
        id: 1,
        label: 'MENUITEMS.MENU.TEXT',
        isTitle: true
    },
    {
        id: 2,
        label: 'MENUITEMS.ACCUEIL.TEXT',
        icon: 'ri-home-4-line',
        link: '/'
    },
    {
        // Accueil des paramètres : cartes par thème, filtrées selon le rôle
        id: 175,
        label: 'MENUITEMS.PARAMETRES.TEXT',
        icon: 'ri-settings-3-line',
        link: '/parametres/accueil',
        actifSur: ['/parametres'],
        roles: GESTIONNAIRES
    },
]
