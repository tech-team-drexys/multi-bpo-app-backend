from django.contrib import admin, messages
from .models import Fonte, Noticia
import feedparser
from django.utils.timezone import make_aware
from datetime import datetime
from django.utils.html import format_html
from django.utils.safestring import mark_safe

def importar_noticias(modeladmin, request, queryset):
    for fonte in queryset:
        feed = feedparser.parse(fonte.feed_url)
        count = 0
        for entry in feed.entries:
            link = entry.link
            titulo = entry.title
            resumo = getattr(entry, 'summary', '')[:1000]
            
            # Se o feed tiver published_parsed, convertemos para datetime
            if hasattr(entry, 'published_parsed'):
                publicado_em = make_aware(datetime(*entry.published_parsed[:6]))
            else:
                publicado_em = make_aware(datetime.now())
            
            # Cria a notícia apenas se não existir duplicada
            noticia, created = Noticia.objects.get_or_create(
                fonte=fonte,
                link=link,
                defaults={
                    'titulo': titulo,
                    'resumo': resumo,
                    'publicado_em': publicado_em,
                }
            )
            if created:
                count += 1
        messages.info(request, f'{count} notícias importadas da fonte "{fonte.nome}"')

importar_noticias.short_description = "Importar notícias do feed selecionado"

@admin.register(Fonte)
class FonteAdmin(admin.ModelAdmin):
    list_display = ("nome", "feed_url", "categoria_padrao", "ativo", "criado_em")
    list_filter = ("ativo", "categoria_padrao", "criado_em")
    search_fields = ("nome", "feed_url")
    ordering = ("-criado_em",)
    actions = [importar_noticias]  # adiciona a ação no admin


@admin.register(Noticia)
class NoticiaAdmin(admin.ModelAdmin):
    list_display = ("titulo", "fonte", "categoria_fonte", "publicado_em", "criado_em", "resumo_formatado", "link_original")
    list_filter = ("fonte", "publicado_em", "criado_em")
    search_fields = ("titulo", "resumo", "link")
    date_hierarchy = "publicado_em"
    ordering = ("-publicado_em",)

    def link_original(self, obj):
        return format_html('<a href="{}" target="_blank">Abrir</a>', obj.link)
    link_original.short_description = "Link Original"

    def resumo_formatado(self, obj):
        if obj.resumo:
            # Renderiza o HTML do resumo como seguro no admin
            return mark_safe(obj.resumo)
        return ""
    resumo_formatado.short_description = "Resumo"

    def categoria_fonte(self, obj):
        return obj.fonte.categoria_padrao
    categoria_fonte.short_description = "Categoria"

