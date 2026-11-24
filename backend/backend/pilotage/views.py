from rest_framework.response import Response
from rest_framework.views import APIView

from api.permissions import IsAuthenticated

from .indicateurs import profils_accessibles, tableau_de_bord


class ProfilsView(APIView):
    """GET /tableaux-de-bord/ : tableaux accessibles à l'utilisateur."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(profils_accessibles(request.user))


class TableauDeBordView(APIView):
    """
    GET /tableaux-de-bord/{profil}/?du=&au=&type_demande=&statut=&departement=&agence=&categorie=&demandeur=
    profil : collaborateur, valideur, direction, comptabilite, administrateur.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, profil):
        return Response(tableau_de_bord(request.user, profil, request.query_params))
