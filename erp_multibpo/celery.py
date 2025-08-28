import os
from celery import Celery

# Configura o settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_multibpo.settings.development')

app = Celery('erp_multibpo')

# Carrega as configurações do Django para Celery
app.config_from_object('django.conf:settings', namespace='CELERY')

# Descobre tasks automaticamente em todos os apps do INSTALLED_APPS
app.autodiscover_tasks()
