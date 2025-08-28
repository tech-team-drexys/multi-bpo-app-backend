from django.db import models

class Fonte(models.Model):
    nome = models.CharField(max_length=100)
    feed_url = models.URLField(unique=True)
    categoria_padrao = models.CharField(max_length=50, blank=True, null=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome
    
class Noticia(models.Model):
    fonte = models.ForeignKey(Fonte, on_delete=models.CASCADE, related_name="noticias")
    titulo = models.CharField(max_length=255)
    resumo = models.TextField(blank=True, null=True)
    conteudo_completo = models.TextField(blank=True, null=True)  # NOVO CAMPO
    categoria = models.CharField(max_length=50, blank=True, null=True)  # NOVO CAMPO
    link = models.URLField()
    imagem = models.URLField(blank=True, null=True)
    publicado_em = models.DateTimeField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("link", "fonte")

    def __str__(self):
        return self.titulo

