#!/bin/bash
set -e

# Création des répertoires nécessaires
mkdir -p "${CA_BASE_PATH:-/app/data}"
mkdir -p "${CA_BASE_PATH:-/app/data}/downloads"
mkdir -p "${CA_BASE_PATH:-/app/data}/processed"

# Installer les dépendances Python
pip install --no-cache-dir -r requirements.txt

# Vérifier si le fichier tva_rules.json existe, sinon créer un par défaut
if [ ! -f "/app/tva_rules.json" ]; then
  echo "Creating default tva_rules.json file"
  cat > /app/tva_rules.json << EOF
{
  "tva_rates": {
    "standard": 20.0,
    "intermédiaire": 10.0,
    "réduit": 5.5,
    "particulier": 7.0,
    "exonéré": 0.0
  },
  "keywords": {
    "standard": ["ovh", "amazon"],
    "intermédiaire": ["restaurant", "resto"],
    "réduit": ["alimentation"],
    "particulier": ["rénovation"],
    "exonéré": ["formation", "impôt"]
  }
}
EOF
fi

# Exécuter la commande principale
exec "$@" 