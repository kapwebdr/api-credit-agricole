# Utiliser Python 3.10 comme image de base
FROM python:3.10-slim

# Informations sur le mainteneur
LABEL maintainer="Damien DJ <contact@kapweb.com>"

# Définir des variables d'environnement pour Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    TZ=Europe/Paris

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libxml2-dev \
    libxslt-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copier le fichier requirements.txt
COPY requirements.txt .

# Installer les dépendances Python
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copier le reste des fichiers de l'application
COPY . .

# Créer les répertoires nécessaires
RUN mkdir -p /data/output /data/logs

# Accorder les permissions d'exécution au script d'entrée
RUN if [ -f docker-entrypoint.sh ]; then chmod +x docker-entrypoint.sh; fi

# Exposer le port utilisé par l'API FastAPI
EXPOSE 8000

# Commande par défaut (peut être remplacée dans docker-compose.yml)
CMD ["uvicorn", "ca_api:app", "--host", "0.0.0.0", "--port", "8000"]

# Alternative: utiliser le script d'entrée s'il existe
# ENTRYPOINT ["/app/docker-entrypoint.sh"] 