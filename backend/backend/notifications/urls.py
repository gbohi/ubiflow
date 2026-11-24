from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AppareilsView, NotificationViewSet, PreferencesView

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
urlpatterns = [path('notifications/preferences/', PreferencesView.as_view()),
               path('notifications/appareils/', AppareilsView.as_view())] + router.urls
