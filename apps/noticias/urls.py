from django.urls import path
from .views import NoticiasListView, NoticiaDetailView, CategoriasListView

urlpatterns = [
    path('noticias/', NoticiasListView.as_view(), name='noticias-list'),
    path('noticias/<int:pk>/', NoticiaDetailView.as_view(), name='noticia-detail'),
    path('categorias/', CategoriasListView.as_view(), name='categorias-list'),  # NOVA URL
]