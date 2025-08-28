import feedparser
from datetime import datetime
from django.utils.timezone import make_aware
from celery import shared_task
from .models import Fonte, Noticia
import requests
from bs4 import BeautifulSoup
import time


def extrair_conteudo_completo_web(url, timeout=10):
    """Extrai conteúdo completo fazendo scraping da página original"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Tentar diferentes seletores comuns para artigos
        content_selectors = [
            'article',
            '.post-content',
            '.entry-content', 
            '.article-content',
            '.content',
            '[class*="content"]',
            'main',
        ]
        
        content = None
        for selector in content_selectors:
            elements = soup.select(selector)
            if elements:
                content = elements[0]
                break
        
        if content:
            # Remover elementos indesejados
            for unwanted in content.select('script, style, nav, footer, aside, .ads, .advertisement'):
                unwanted.decompose()
            
            # Extrair texto mantendo parágrafos
            paragraphs = content.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            text_content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
            
            return text_content[:15000] if text_content else None
            
    except Exception as e:
        print(f"Erro no web scraping para {url}: {e}")
        return None

def extrair_imagem_feed(entry):
    """Extrai URL da imagem de diferentes fontes do feed RSS"""
    imagem_url = None
    
    # Método 1: entry.enclosures (anexos)
    if hasattr(entry, 'enclosures') and entry.enclosures:
        for enclosure in entry.enclosures:
            if hasattr(enclosure, 'type') and enclosure.type.startswith('image/'):
                imagem_url = enclosure.href
                break
    
    # Método 2: entry.media_content (Yahoo Media RSS)
    if not imagem_url and hasattr(entry, 'media_content'):
        for media in entry.media_content:
            if media.get('type', '').startswith('image/'):
                imagem_url = media.get('url')
                break
    
    # Método 3: Buscar no conteúdo HTML (content, summary, description)
    if not imagem_url:
        import re
        textos_busca = []
        
        # NOVO: Verificar content primeiro (onde estão as imagens!)
        if hasattr(entry, 'content') and entry.content:
            content_text = entry.content[0].value if isinstance(entry.content, list) else entry.content
            textos_busca.append(content_text)
        
        # Verificar summary
        if hasattr(entry, 'summary'):
            textos_busca.append(entry.summary)
        
        # Verificar description
        if hasattr(entry, 'description'):
            textos_busca.append(entry.description)
            
        for texto_busca in textos_busca:
            if texto_busca and '<img' in texto_busca:
                # Buscar tag <img src="...">
                img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', texto_busca, re.IGNORECASE)
                if img_match:
                    imagem_url = img_match.group(1)
                    break
    
    # Método 4: entry.image (alguns feeds têm este campo)
    if not imagem_url and hasattr(entry, 'image'):
        if isinstance(entry.image, str):
            imagem_url = entry.image
        elif hasattr(entry.image, 'href'):
            imagem_url = entry.image.href
    
    return imagem_url

# Task para importar notícias automaticamente
@shared_task
def importar_noticias_task():
    fontes = Fonte.objects.filter(ativo=True)
    total_importadas = 0

    for fonte in fontes:
        feed = feedparser.parse(fonte.feed_url)
        count = 0
        for entry in feed.entries:
            link = entry.link
            titulo = entry.title
            resumo = getattr(entry, 'summary', '')[:1000]
            
            # NOVO: Extrair conteúdo completo
            conteudo_completo = ''
            if hasattr(entry, 'content') and entry.content:
                conteudo_completo = entry.content[0].value if isinstance(entry.content, list) else entry.content
            elif hasattr(entry, 'description') and entry.description:
                conteudo_completo = entry.description
            elif resumo:
                conteudo_completo = resumo

            # Se conteúdo ainda está vazio ou muito pequeno, tentar web scraping
            if not conteudo_completo or len(conteudo_completo.strip()) < 200:
                print(f"Tentando web scraping para: {titulo}")
                scraped_content = extrair_conteudo_completo_web(link)
                if scraped_content:
                    conteudo_completo = scraped_content

            # Limitar tamanho
            if conteudo_completo:
                conteudo_completo = conteudo_completo[:15000]

            # NOVO: Extrair imagem
            imagem_url = extrair_imagem_feed(entry)

            if hasattr(entry, 'published_parsed'):
                publicado_em = make_aware(datetime(*entry.published_parsed[:6]))
            else:
                publicado_em = make_aware(datetime.now())

            noticia, created = Noticia.objects.get_or_create(
                fonte=fonte,
                link=link,
                defaults={
                    'titulo': titulo,
                    'resumo': resumo,
                    'conteudo_completo': conteudo_completo,  # NOVO CAMPO
                    'categoria': fonte.categoria_padrao,     # NOVO CAMPO
                    'imagem': imagem_url,                    # NOVO CAMPO
                    'publicado_em': publicado_em,
                }
            )
            if created:
                count += 1
        total_importadas += count
        print(f'{count} notícias importadas da fonte "{fonte.nome}"')

    print(f'Total de notícias importadas: {total_importadas}')


# Agendamento Celery Beat
CELERY_BEAT_SCHEDULE = {
    'importar-noticias-a-cada-30-minutos': {
        'task': 'apps.noticias.tasks.importar_noticias_task',
        'schedule': 30 * 60.0,  # 30 minutos
    },
}