#!/bin/bash
set -e

# Configuration de l'environnement
echo "Configuration de l'environnement pour l'API Crédit Agricole..."

# Créer les répertoires nécessaires s'ils n'existent pas
mkdir -p /data/output
mkdir -p /data/logs

# Vérifier si le fichier .env existe, sinon en créer un par défaut
if [ ! -f ".env" ]; then
    echo "Création d'un fichier .env par défaut..."
    cat > .env << EOF
# Informations d'identification Crédit Agricole
CA_USERNAME=
CA_PASSWORD=
CA_DEPARTMENT=

# Chemins de fichiers
CA_BASE_PATH=/data
CA_DOWNLOAD_PATH=
CA_OUTPUT_DIR=

# Configuration des comptes
CA_ACCOUNTS=

# Format du fichier à télécharger (xlsx, pdf, csv)
CA_FILE_EXTENSION=xlsx

# Clés API
API_KEY=
DEBUG_MODE=False
EOF
    echo "Fichier .env créé. Veuillez le configurer avec vos informations."
fi

# Tester les dépendances Python
echo "Vérification des dépendances Python..."
pip list

# Vérifier si on peut lancer en mode API ou CLI
if [ "$1" = "api" ]; then
    echo "Démarrage en mode API..."
    exec uvicorn ca_api:app --host 0.0.0.0 --port 8000 --reload
elif [ "$1" = "download" ]; then
    echo "Exécution du téléchargement des relevés..."
    exec python get_credit_agricole.py "${@:2}"
elif [ "$1" = "process" ]; then
    echo "Traitement des relevés téléchargés..."
    exec python process_ca_pdf.py "${@:2}"
else
    # Mode par défaut: API
    echo "Démarrage de l'API Crédit Agricole..."
    exec uvicorn ca_api:app --host 0.0.0.0 --port 8000
fi 