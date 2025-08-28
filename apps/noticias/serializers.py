from rest_framework import serializers
from .models import Noticia, Fonte

class FonteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fonte
        fields = ['id', 'nome', 'categoria_padrao']

class NoticiaSerializer(serializers.ModelSerializer):
    fonte = FonteSerializer(read_only=True)

    class Meta:
        model = Noticia
        fields = ['id', 'titulo', 'resumo', 'conteudo_completo', 'categoria', 'link', 'imagem', 'publicado_em', 'fonte']