from rest_framework.routers import DefaultRouter

from .views import JournalViewSet

router = DefaultRouter()
router.register(r'journal', JournalViewSet, basename='journal')
urlpatterns = router.urls
