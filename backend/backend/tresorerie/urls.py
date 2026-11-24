from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'tresorerie/a-payer', views.APayerViewSet, basename='a-payer')
router.register(r'tresorerie/reglements', views.ReglementViewSet, basename='reglement')
router.register(r'tresorerie/reversements', views.ReversementViewSet, basename='reversement')
urlpatterns = router.urls
