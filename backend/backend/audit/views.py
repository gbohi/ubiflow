import django_filters
from rest_framework import mixins, permissions, serializers, viewsets

from api.permissions import ROLE_CONTROLEUR, get_roles, is_admin

from .models import JournalActivite


class JournalSerializer(serializers.ModelSerializer):
    auteur_nom = serializers.SerializerMethodField()
    pour_compte_de_nom = serializers.SerializerMethodField()

    class Meta:
        model = JournalActivite
        fields = '__all__'

    @staticmethod
    def _nom(u):
        return (f"{u.nom} {u.prenom}".strip() or u.username) if u else None

    def get_auteur_nom(self, obj):
        return self._nom(obj.auteur)

    def get_pour_compte_de_nom(self, obj):
        return self._nom(obj.pour_compte_de)


class LectureJournal(permissions.BasePermission):
    message = "Journal réservé aux administrateurs et contrôleurs."

    def has_permission(self, request, view):
        return is_admin(request.user) or ROLE_CONTROLEUR in get_roles(request.user)


class JournalFilter(django_filters.FilterSet):
    du = django_filters.DateFilter(field_name='horodatage', lookup_expr='date__gte')
    au = django_filters.DateFilter(field_name='horodatage', lookup_expr='date__lte')
    action = django_filters.CharFilter(lookup_expr='istartswith')

    class Meta:
        model = JournalActivite
        fields = ['auteur', 'objet_type', 'objet_id']


class JournalViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /journal/?du=&au=&action=&auteur=&objet_type=&search="""
    queryset = JournalActivite.objects.select_related('auteur', 'pour_compte_de')
    serializer_class = JournalSerializer
    permission_classes = [LectureJournal]
    filterset_class = JournalFilter
    search_fields = ['objet_libelle', 'motif', 'action', 'auteur__nom', 'auteur__username']
