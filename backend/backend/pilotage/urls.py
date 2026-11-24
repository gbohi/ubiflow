from django.urls import path

from . import views

urlpatterns = [
    path('tableaux-de-bord/', views.ProfilsView.as_view()),
    path('tableaux-de-bord/<str:profil>/', views.TableauDeBordView.as_view()),
]
