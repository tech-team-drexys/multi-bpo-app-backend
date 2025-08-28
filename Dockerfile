# Dockerfile para Backend Django - ERP MULTIBPO
FROM python:3.10-slim

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema (adicionando curl)
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements primeiro (para cache eficiente do Docker)
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar todo o código fonte
COPY . .

# Expor porta do Django
EXPOSE 8002

# Comando padrão (pode ser sobrescrito no docker-compose se necessário)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8002"]
