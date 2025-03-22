# API Crédit Agricole

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10-green.svg)

Cette API permet d'automatiser la gestion des relevés bancaires du Crédit Agricole et le traitement de la TVA pour les micro-entrepreneurs et professionnels.

## 📋 Fonctionnalités

- ✅ Téléchargement automatique des relevés bancaires du Crédit Agricole
- ✅ Traitement des fichiers Excel pour extraire les transactions
- ✅ Calcul automatique de la TVA selon les règles configurables
- ✅ Génération de rapports et synthèses pour la déclaration fiscale
- ✅ Interface API RESTful pour l'intégration avec d'autres services
- ✅ Déploiement facile avec Docker

## 🚀 Installation

### Prérequis

- Python 3.10 ou supérieur
- Pip (gestionnaire de paquets Python)
- Compte Crédit Agricole avec accès en ligne
- Docker et Docker Compose (pour l'installation avec Docker)

### Installation locale

1. Clonez ce dépôt :
   ```bash
   git clone https://github.com/kapwebdr/api-credit-agricole.git
   cd api-credit-agricole
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

3. Copiez le fichier `.env.example` vers `.env` et configurez-le avec vos informations :
   ```bash
   cp .env.example .env
   nano .env
   ```

### Installation avec Docker

1. Clonez ce dépôt comme indiqué ci-dessus

2. Copiez et configurez le fichier `.env` :
   ```bash
   cp .env.example .env
   nano .env
   ```

3. Lancez l'application avec Docker Compose :
   ```bash
   docker-compose up -d
   ```

Pour voir les logs :
```bash
docker-compose logs -f
```

Pour arrêter l'application :
```bash
docker-compose down
```

## ⚙️ Configuration

### Fichier d'environnement (.env)

Le fichier `.env` doit contenir les informations suivantes :

```
# Informations Crédit Agricole
CA_USERNAME=votre_identifiant
CA_PASSWORD=votre_mot_de_passe
CA_DEPARTMENT=votre_departement
CA_ACCOUNT_NUMBERS=compte1,compte2,compte3

# Chemin pour stocker les fichiers
CA_BASE_PATH=/chemin/vers/dossier/compta
CA_FILE_EXTENSION=xlsx

# Sécurité API
CA_API_KEY=votre_cle_api_secrete

# Debug
CA_DEBUG_MODE=true
```

### Règles TVA

Les règles de TVA sont configurées dans le fichier `tva_rules.json`. Un exemple est fourni dans `tva_rules.example.json`. Ces règles définissent :

1. Les taux de TVA applicables
2. Les mots-clés permettant de catégoriser automatiquement les transactions

Exemple de structure :
```json
{
  "tva_rates": {
    "standard": 20.0,
    "réduit": 5.5,
    "exonéré": 0.0
  },
  "keywords": {
    "standard": ["ovh", "amazon"],
    "réduit": ["alimentation"],
    "exonéré": ["formation", "impôt"]
  }
}
```

## 🚀 Démarrage de l'API

### Démarrage en local

```bash
python ca_api.py
```

### Démarrage avec Docker

```bash
docker-compose up -d
```

Par défaut, l'API démarre sur http://localhost:8000.

## 📖 Documentation de l'API

La documentation interactive Swagger est disponible à l'adresse http://localhost:8000/docs une fois l'API démarrée.

### Authentification

Toutes les requêtes (sauf `/health`) nécessitent un en-tête d'authentification :

```
X-API-Key: votre_cle_api_secrete
```

### Points d'accès disponibles

#### Système
- `GET /health` - Vérifie que l'API fonctionne correctement
- `GET /debug` - Affiche des informations de débogage (nécessite CA_DEBUG_MODE=true)

#### Comptes
- `GET /accounts` - Récupère la liste des comptes configurés

#### Téléchargement
- `POST /download` - Télécharge les relevés bancaires
  ```json
  {
    "account_number": "70089352734",  // optionnel
    "start_date": "01/01/2023",       // optionnel
    "end_date": "31/01/2023",         // optionnel
    "force": false                    // optionnel
  }
  ```

#### Traitement
- `POST /process` - Traite les relevés bancaires téléchargés
  ```json
  {
    "account_number": "70089352734",  // optionnel
    "file_path": "/chemin/vers/fichier.xlsx"  // optionnel
  }
  ```

#### Débogage
- `POST /validate-request` - Valide une requête sans l'exécuter (pour le débogage)
  ```json
  {
    "request_type": "download",  // ou "process"
    "data": {
      // Les mêmes champs que pour /download ou /process
    }
  }
  ```

#### Règles TVA
- `GET /tva-rules` - Récupère les règles TVA actuelles
- `POST /tva-rules` - Met à jour l'ensemble des règles TVA
- `PUT /tva-rules/{type}` - Met à jour une règle TVA spécifique
- `POST /tva-rules/{type}` - Crée une nouvelle règle TVA
- `DELETE /tva-rules/{type}` - Supprime une règle TVA

## 🔧 Exemples d'utilisation

### Télécharger les relevés de tous les comptes

```bash
curl -X POST http://localhost:8000/download \
  -H "X-API-Key: votre_cle_api_secrete" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Télécharger le relevé d'un compte spécifique

```bash
curl -X POST http://localhost:8000/download \
  -H "X-API-Key: votre_cle_api_secrete" \
  -H "Content-Type: application/json" \
  -d '{"account_number": "70089352734"}'
```

### Traiter les relevés téléchargés

```bash
curl -X POST http://localhost:8000/process \
  -H "X-API-Key: votre_cle_api_secrete" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Valider une requête de téléchargement

```bash
curl -X POST http://localhost:8000/validate-request \
  -H "X-API-Key: votre_cle_api_secrete" \
  -H "Content-Type: application/json" \
  -d '{"request_type": "download", "data": {"account_number": "70089352734"}}'
```

### Ajouter une nouvelle règle TVA

```bash
curl -X POST http://localhost:8000/tva-rules/super_reduit \
  -H "X-API-Key: votre_cle_api_secrete" \
  -H "Content-Type: application/json" \
  -d '{"type": "super_reduit", "rate": 2.1, "keywords": ["livre", "presse", "médicament"]}'
```

## 🔍 Débogage

Si vous rencontrez des erreurs 422 (Unprocessable Entity) ou d'autres problèmes avec l'API, vous pouvez activer le mode débogage :

1. Définissez `CA_DEBUG_MODE=true` dans votre fichier `.env`
2. Consultez le fichier de log `api_debug.log` pour plus de détails
3. Utilisez l'endpoint `/debug` pour vérifier la configuration
4. Testez vos requêtes avec l'endpoint `/validate-request` pour vérifier leur validité

### Erreurs 422 (Unprocessable Entity)

Cette erreur se produit généralement lorsque :
- Les données envoyées ne correspondent pas au format attendu
- Un champ obligatoire est manquant
- Un champ a un type de données incorrect

Pour résoudre ce problème :
1. Vérifiez le format de vos données JSON
2. Utilisez l'endpoint `/validate-request` pour tester vos requêtes
3. Consultez les logs pour voir les erreurs de validation détaillées

## 🔄 Flux de travail type

1. **Configuration initiale** :
   - Configurez vos identifiants dans le fichier `.env`
   - Personnalisez les règles TVA dans `tva_rules.json`

2. **Téléchargement mensuel** :
   - Lancez le téléchargement des relevés via l'API
   - Les fichiers sont sauvegardés dans le dossier configuré

3. **Traitement et analyse** :
   - Traitez les fichiers téléchargés
   - Consultez la synthèse TVA générée

4. **Déclaration fiscale** :
   - Utilisez les informations de la synthèse pour votre déclaration
   - Conservez les fichiers générés comme justificatifs

## 🛡️ Sécurité

- L'API est protégée par une clé d'API
- Les identifiants bancaires sont stockés localement dans le fichier `.env`
- Aucune donnée n'est envoyée à des serveurs externes

## 📝 Notes importantes

- Cette application utilise l'API non officielle du Crédit Agricole
- L'outil est conçu pour les micro-entrepreneurs et petites entreprises
- Le calcul de la TVA est fourni à titre indicatif et ne remplace pas l'avis d'un expert-comptable

## 🤝 Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à ouvrir une issue ou une pull request.

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails. 