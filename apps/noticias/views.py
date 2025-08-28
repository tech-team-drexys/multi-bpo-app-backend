from rest_framework import generics, filters
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.db.models import Q
from .models import Noticia, Fonte
from .serializers import NoticiaSerializer
from django_filters.rest_framework import DjangoFilterBackend

class NoticiasListView(generics.ListAPIView):
    queryset = Noticia.objects.all().order_by('-publicado_em')
    serializer_class = NoticiaSerializer
    permission_classes = [AllowAny]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    
    # Filtragem
    filterset_fields = ['fonte__id', 'fonte__categoria_padrao', 'categoria']  # ADICIONADO categoria
    search_fields = ['titulo', 'resumo']
    ordering_fields = ['publicado_em', 'titulo']
    ordering = ['-publicado_em']

class NoticiaDetailView(generics.RetrieveAPIView):
    queryset = Noticia.objects.all()
    serializer_class = NoticiaSerializer
    permission_classes = [AllowAny]
    lookup_field = 'pk'

# NOVA VIEW PARA CATEGORIAS
class CategoriasListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    
    def get(self, request, *args, **kwargs):
        # Buscar categorias únicas das fontes ativas
        categorias_fontes = Fonte.objects.filter(
            ativo=True, 
            categoria_padrao__isnull=False
        ).values_list('categoria_padrao', flat=True).distinct()
        
        # Buscar categorias únicas das notícias (caso existam)
        categorias_noticias = Noticia.objects.filter(
            categoria__isnull=False
        ).values_list('categoria', flat=True).distinct()
        
        # Combinar e remover duplicatas
        todas_categorias = set(list(categorias_fontes) + list(categorias_noticias))
        categorias_lista = sorted([cat for cat in todas_categorias if cat.strip()])
        
        return Response({
            "results": categorias_lista
        })