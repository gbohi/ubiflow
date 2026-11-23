import { ActionReducerMap } from "@ngrx/store";
import { AuthenticationState, authenticationReducer } from "./Authentication/authentication.reducer";
import { LayoutState, layoutReducer } from "./layouts/layout-reducers";

import { StatutReducer, StatutState } from "./Statut/statut.reducer";
import { AgenceReducer, AgenceState } from "./Agence/agence.reducer";
import { DepartementReducer, DepartementState } from "./Departement/departement.reducer";
import { RoleReducer, RoleState } from "./Role/role.reducer";
import { UserReducer, UserState } from "./User/user.reducer";
import { FonctionReducer, FonctionState } from "./Fonction/fonction.reducer";
import { CategoriesalarieReducer, CategoriesalarieState } from "./Categoriesalarie/categoriesalarie.reducer";
import { PosteReducer, PosteState } from './Poste/poste.reducer';
import { userServiceReducer, UserServiceState } from './UserService/user-service.reducer';
import { userAgenceReducer, UserAgenceState } from './UserAgence/user-agence.reducer';
import { userPosteReducer, UserPosteState } from './UserPoste/user-poste.reducer';
import { userCategoriesalarieReducer, UserCategoriesalarieState } from './UserCategoriesalarie/user-categoriesalarie.reducer';


export interface RootReducerState {
    layout: LayoutState,
    auth: AuthenticationState;
    statut: StatutState;
    agence: AgenceState;
    departement: DepartementState;
    role: RoleState;
    user: UserState;
    fonction: FonctionState,
    categoriesalarie: CategoriesalarieState,
    poste: PosteState,
    userService: UserServiceState,
    userAgence: UserAgenceState,
    userPoste: UserPosteState,
    userCategoriesalarie: UserCategoriesalarieState;
}

export const rootReducer: ActionReducerMap<RootReducerState> = {
    layout: layoutReducer,
    auth: authenticationReducer,
    statut: StatutReducer,
    agence: AgenceReducer,
    departement: DepartementReducer,
    role: RoleReducer,
    user: UserReducer,
    fonction: FonctionReducer,
    categoriesalarie: CategoriesalarieReducer,
    poste: PosteReducer,
    userService: userServiceReducer,
    userAgence: userAgenceReducer,
    userPoste: userPosteReducer,
    userCategoriesalarie: userCategoriesalarieReducer,
}