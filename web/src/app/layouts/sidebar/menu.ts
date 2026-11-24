import { MenuItem } from "./menu.model";

import { GESTIONNAIRES } from "../../core/helpers/roles";

const ADMIN_WORKFLOW = ['super_admin', 'admin', 'admin_workflow'];
const JOURNAL = ['super_admin', 'admin', 'controleur'];
const TRESORERIE = ['super_admin', 'admin', 'comptable', 'admin_finances'];
const FINANCES = ['super_admin', 'admin', 'admin_finances', 'comptable', 'controleur'];


export const MENU: MenuItem[] = [
    { id: 1, label: 'MENUITEMS.MENU.TEXT', isTitle: true },
    { id: 2, label: 'MENUITEMS.ACCUEIL.TEXT', icon: 'ri-home-4-line', link: '/' },
    { id: 10, label: 'Mes demandes', icon: 'ri-file-list-3-line', link: '/demandes', actifSur: ['/demandes'] },
    { id: 11, label: 'Nouvelle demande', icon: 'ri-add-circle-line', link: '/demandes/nouvelle' },
    { id: 12, label: 'À valider', icon: 'ri-checkbox-multiple-line', link: '/validations' },
    { id: 13, label: 'Délégations', icon: 'ri-user-shared-line', link: '/delegations' },
    { id: 15, label: 'Trésorerie', isTitle: true, roles: TRESORERIE },
    { id: 16, label: 'À payer', icon: 'ri-wallet-3-line', link: '/tresorerie/a-payer', roles: TRESORERIE },
    { id: 18, label: 'Clôtures à contrôler', icon: 'ri-file-check-line', link: '/tresorerie/clotures', roles: [...TRESORERIE, 'controleur'] },
    { id: 17, label: 'Reversements', icon: 'ri-arrow-go-back-line', link: '/tresorerie/reversements', roles: TRESORERIE },
    { id: 20, label: 'Administration', isTitle: true, roles: [...new Set([...GESTIONNAIRES, ...ADMIN_WORKFLOW, ...JOURNAL, ...FINANCES])] },
    { id: 21, label: 'Types de demande', icon: 'ri-file-settings-line', link: '/parametres/types-demande', roles: ADMIN_WORKFLOW },
    { id: 22, label: 'Circuits de validation', icon: 'ri-git-merge-line', link: '/parametres/workflows', actifSur: ['/parametres/workflows'], roles: ADMIN_WORKFLOW },
    { id: 24, label: 'Barèmes', icon: 'ri-scales-3-line', link: '/parametres/baremes', roles: FINANCES },
    { id: 25, label: 'Lieux et distances', icon: 'ri-map-pin-line', link: '/parametres/lieux', roles: FINANCES },
    { id: 23, label: "Journal d'activité", icon: 'ri-history-line', link: '/parametres/journal', roles: JOURNAL },
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
