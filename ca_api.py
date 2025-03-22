from fastapi import FastAPI, Depends, HTTPException, Header, status, Body, Request, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse
from typing import List, Dict, Optional, Any
import os
import json
import asyncio
import uvicorn
from pydantic import BaseModel, ValidationError
import ca_common
from datetime import datetime
import subprocess
import sys
import traceback
import logging
import pandas as pd

# Configuration du logger
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api_debug.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ca_api")

# Initialiser l'application FastAPI
app = FastAPI(
    title="Crédit Agricole API",
    description="API pour gérer les téléchargements et traitements des relevés bancaires du Crédit Agricole",
    version="1.0.0"
)

# Charger les variables d'environnement
ca_common.load_environment()

# Configuration de la sécurité API Key
API_KEY = os.getenv("CA_API_KEY")
if not API_KEY:
    raise ValueError("La clé d'API n'est pas définie dans le fichier .env")

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Mode debug
DEBUG_MODE = os.getenv("CA_DEBUG_MODE", "false").lower() == "true"

# Modèles de données pour les requêtes et réponses
class DownloadRequest(BaseModel):
    account_number: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    force: bool = False
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_number": "12345678901",
                "start_date": "01/01/2023",
                "end_date": "31/01/2023",
                "force": False
            }
        }

class ProcessRequest(BaseModel):
    account_number: Optional[str] = None
    file_path: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "account_number": "12345678901",
                "file_path": "/chemin/vers/fichier.xlsx"
            }
        }

class TVARule(BaseModel):
    type: str
    rate: float
    keywords: List[str]

class TVARules(BaseModel):
    tva_rates: Dict[str, float]
    keywords: Dict[str, List[str]]

class DownloadResponse(BaseModel):
    success: bool
    message: str
    files: List[str]
    data: Dict[str, Dict[str, Any]]

# Middleware pour capturer les exceptions de validation
@app.middleware("http")
async def validation_exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except ValidationError as exc:
        logger.error(f"Erreur de validation: {exc}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": f"Erreur de validation: {exc}"}
        )
    except Exception as exc:
        logger.error(f"Exception non gérée: {exc}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)}
        )

# Fonction de vérification de l'API key
async def verify_api_key(api_key: str = Header(None, alias=API_KEY_NAME)):
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key manquante",
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key invalide",
        )
    return api_key

# Routes de l'API
@app.get("/health", tags=["Système"])
async def health_check():
    """Vérifie que l'API fonctionne correctement"""
    return {"status": "ok", "timestamp": datetime.now().isoformat(), "debug_mode": DEBUG_MODE}

@app.get("/debug", tags=["Système"], dependencies=[Depends(verify_api_key)])
async def debug_info():
    """Affiche des informations de débogage (uniquement en mode debug)"""
    if not DEBUG_MODE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Le mode debug n'est pas activé"
        )
    
    # Collecter des informations utiles pour le débogage
    try:
        env_vars = {k: v for k, v in os.environ.items() if k.startswith('CA_')}
        # Masquer le mot de passe
        if 'CA_PASSWORD' in env_vars:
            env_vars['CA_PASSWORD'] = '******'
        
        accounts = ca_common.get_account_numbers()
        
        # Vérifier l'existence des scripts
        scripts = {
            "get_credit_agricole.py": os.path.exists("get_credit_agricole.py"),
            "process_ca_pdf.py": os.path.exists("process_ca_pdf.py"),
            "ca_common.py": os.path.exists("ca_common.py")
        }
        
        # Vérifier l'existence du répertoire de base
        base_path = os.getenv("CA_BASE_PATH", "")
        base_path_exists = os.path.exists(base_path) if base_path else False
        
        # Vérifier l'existence des règles TVA
        tva_rules_exists = os.path.exists("tva_rules.json")
        
        return {
            "debug_info": {
                "environment": env_vars,
                "accounts": accounts,
                "scripts": scripts,
                "base_path": {
                    "path": base_path,
                    "exists": base_path_exists
                },
                "tva_rules": {
                    "exists": tva_rules_exists
                }
            }
        }
    except Exception as e:
        logger.error(f"Erreur lors de la collecte des informations de débogage: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Erreur lors de la collecte des informations de débogage: {str(e)}",
            "traceback": traceback.format_exc() if DEBUG_MODE else None
        }

@app.get("/accounts", tags=["Comptes"], dependencies=[Depends(verify_api_key)])
async def get_accounts():
    """Récupère la liste des comptes configurés"""
    try:
        accounts = ca_common.get_account_numbers()
        return {"accounts": accounts}
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des comptes: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des comptes: {str(e)}"
        )

@app.post("/download", response_model=DownloadResponse, tags=["Téléchargement"], dependencies=[Depends(verify_api_key)])
async def download_statements(request: DownloadRequest, background_tasks: BackgroundTasks):
    """
    Télécharger les relevés de compte du Crédit Agricole
    """
    logger.info(f"Début de la requête de téléchargement: {request}")
    
    try:
        # Construction de la commande
        cmd = ["python3", ca_common.get_script_path("get_credit_agricole.py")]
        
        if request.account_number:
            cmd.extend(["--account", request.account_number])
        
        if request.start_date:
            cmd.extend(["--start-date", request.start_date])
        
        if request.end_date:
            cmd.extend(["--end-date", request.end_date])
        
        if request.force:
            cmd.append("--force")
        
        logger.debug(f"Commande à exécuter: {' '.join(cmd)}")
        
        # Exécution du script en subprocess
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        stdout_str = stdout.decode()
        stderr_str = stderr.decode()
        
        logger.debug(f"Sortie standard: {stdout_str}")
        if stderr_str:
            logger.warning(f"Erreur standard: {stderr_str}")
        
        # Vérification du code de retour
        if process.returncode != 0:
            error_msg = f"Échec du téléchargement (code: {process.returncode}): {stderr_str}"
            logger.error(error_msg)
            return DownloadResponse(
                success=False,
                message=error_msg,
                files=[]
            )
        
        # Extraction des fichiers générés à partir de la sortie standard
        files = []
        for line in stdout_str.splitlines():
            if "Fichier téléchargé:" in line:
                file_path = line.split("Fichier téléchargé:")[1].strip()
                files.append(file_path)
        
        if not files:
            # Le script s'est terminé avec succès mais aucun fichier n'a été téléchargé
            # (peut-être que tous existaient déjà et --force n'a pas été utilisé)
            return DownloadResponse(
                success=True,
                message="Aucun nouveau fichier téléchargé. Les fichiers existent peut-être déjà.",
                files=[]
            )
        
        # Analyse des fichiers téléchargés pour extraire les données
        data_by_account = {}
        
        for file_path in files:
            try:
                # Extraire le numéro de compte du nom de fichier
                file_name = os.path.basename(file_path)
                account_number = file_name.split('.')[0]
                
                # Lire le fichier Excel
                df = pd.read_excel(file_path, header=None)
                
                # Détecter la ligne d'en-tête (généralement après "Date")
                header_row = None
                for i in range(min(30, len(df))):  # Chercher dans les 30 premières lignes
                    if "Date" in df.iloc[i].values:
                        header_row = i
                        break
                
                if header_row is not None:
                    # Utiliser cette ligne comme en-tête et les données qui suivent
                    headers = df.iloc[header_row].tolist()
                    data = df.iloc[header_row+1:].copy()
                    data.columns = headers
                    
                    # Nettoyer les en-têtes (supprimer les espaces, etc.)
                    clean_headers = [str(h).strip() if isinstance(h, str) else str(h) for h in headers]
                    data.columns = clean_headers
                    
                    # Conversion en dictionnaire pour la réponse JSON
                    data_dict = data.fillna("").to_dict(orient='records')
                    
                    # Conversion des dates au format ISO pour JSON
                    for row in data_dict:
                        for key, value in row.items():
                            if isinstance(value, pd.Timestamp):
                                row[key] = value.strftime('%Y-%m-%d')
                    
                    data_by_account[account_number] = {
                        "headers": clean_headers,
                        "data": data_dict
                    }
                    
                    logger.info(f"Données extraites pour le compte {account_number}: {len(data_dict)} lignes")
                else:
                    logger.warning(f"Impossible de trouver l'en-tête dans le fichier {file_path}")
            except Exception as e:
                logger.error(f"Erreur lors de l'extraction des données du fichier {file_path}: {str(e)}")
                # On continue avec les autres fichiers même si un échoue
        
        # Créer la réponse
        return DownloadResponse(
            success=True,
            message=f"{len(files)} fichier(s) téléchargé(s) avec succès",
            files=files,
            data=data_by_account
        )
            
    except Exception as e:
        error_msg = f"Erreur lors du téléchargement: {str(e)}"
        logger.error(error_msg)
        return DownloadResponse(
            success=False,
            message=error_msg,
            files=[]
        )

@app.post("/process", tags=["Traitement"], dependencies=[Depends(verify_api_key)])
async def process_statements(request: ProcessRequest = Body(...)):
    """
    Traite les relevés bancaires téléchargés
    
    - account_number: Numéro de compte spécifique (optionnel)
    - file_path: Chemin du fichier à traiter (optionnel)
    """
    try:
        logger.info(f"Début de traitement avec les paramètres: {request.dict()}")
        cmd = [sys.executable, "process_ca_pdf.py"]
        
        if request.file_path:
            cmd.extend(["--input", request.file_path])
        elif request.account_number:
            cmd.extend(["--account", request.account_number])
        
        # Logs pour le débogage
        logger.debug(f"Commande de traitement: {' '.join(cmd)}")
        
        # Exécuter le script de traitement dans un processus séparé
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        stdout_text = stdout.decode()
        stderr_text = stderr.decode()
        
        logger.debug(f"Sortie standard: {stdout_text}")
        if stderr_text:
            logger.error(f"Erreur standard: {stderr_text}")
        
        if process.returncode != 0:
            logger.error(f"Échec du traitement avec code: {process.returncode}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors du traitement (code {process.returncode}): {stderr_text}"
            )
        
        # Extraire les chemins des fichiers traités depuis la sortie
        processed_files = []
        for line in stdout_text.splitlines():
            if "Traitement terminé. Fichier généré:" in line:
                # Extraire le chemin du fichier depuis la ligne
                parts = line.split("Traitement terminé. Fichier généré:")
                if len(parts) > 1:
                    file_path = parts[1].strip()
                    processed_files.append(file_path)
            elif "Le traitement a réussi. Fichier généré:" in line:
                parts = line.split("Le traitement a réussi. Fichier généré:")
                if len(parts) > 1:
                    file_path = parts[1].strip()
                    processed_files.append(file_path)
        
        # Si aucun fichier n'a été trouvé mais que le traitement a réussi,
        # essayer de déduire les fichiers traités
        if not processed_files:
            # Obtenir le répertoire dynamique
            dynamic_dir = ca_common.get_dynamic_directory()
            
            # Trouver les fichiers Excel récemment créés dans le répertoire
            import glob
            from datetime import datetime, timedelta
            
            # Chercher les fichiers Excel créés dans les dernières 5 minutes
            recent_time = datetime.now() - timedelta(minutes=5)
            for excel_file in glob.glob(os.path.join(dynamic_dir, "ca_operations_*.xlsx")):
                if os.path.getmtime(excel_file) >= recent_time.timestamp():
                    processed_files.append(excel_file)
        
        # Vérifier si le traitement a réussi en analysant les logs
        success = any("traitement a réussi" in line.lower() or "traitement terminé" in line.lower() for line in stdout_text.splitlines())
        
        # Message résumé
        summary = f"{len(processed_files)} fichiers traités avec succès" if success else "Traitement terminé sans fichiers générés"
        
        logger.info("Traitement terminé avec succès")
        return {
            "status": "success" if success else "completed_with_warnings",
            "message": summary,
            "account": request.account_number or "all",
            "processed_files": processed_files,
            "logs": stdout_text if DEBUG_MODE else None
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Exception lors du traitement: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du traitement: {str(e)}"
        )

@app.post("/validate-request", tags=["Débogage"], dependencies=[Depends(verify_api_key)])
async def validate_request(request_type: str = Body(...), data: dict = Body(...)):
    """
    Valide une requête sans l'exécuter (pour le débogage)
    
    - request_type: Type de requête ('download' ou 'process')
    - data: Données de la requête à valider
    """
    try:
        if request_type == "download":
            # Valider la requête de téléchargement
            request = DownloadRequest(**data)
            return {
                "status": "valid",
                "message": "La requête de téléchargement est valide",
                "parsed_data": request.dict()
            }
        elif request_type == "process":
            # Valider la requête de traitement
            request = ProcessRequest(**data)
            return {
                "status": "valid",
                "message": "La requête de traitement est valide",
                "parsed_data": request.dict()
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type de requête inconnu: {request_type}"
            )
    except ValidationError as e:
        logger.error(f"Erreur de validation: {e}")
        return {
            "status": "invalid",
            "message": "La requête est invalide",
            "errors": e.errors()
        }
    except Exception as e:
        logger.error(f"Exception lors de la validation: {e}")
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Erreur lors de la validation: {str(e)}",
            "traceback": traceback.format_exc() if DEBUG_MODE else None
        }

@app.get("/tva-rules", tags=["TVA"], dependencies=[Depends(verify_api_key)])
async def get_tva_rules():
    """Récupère les règles TVA actuelles"""
    try:
        # Charger les règles TVA depuis le fichier
        with open('tva_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        return rules
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fichier de règles TVA non trouvé"
        )
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des règles TVA: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des règles TVA: {str(e)}"
        )

@app.post("/tva-rules", tags=["TVA"], dependencies=[Depends(verify_api_key)])
async def update_tva_rules(rules: TVARules):
    """Met à jour l'ensemble des règles TVA"""
    try:
        # Sauvegarder les règles TVA dans le fichier
        with open('tva_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules.dict(), f, ensure_ascii=False, indent=2)
        return {"status": "success", "message": "Règles TVA mises à jour avec succès"}
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour des règles TVA: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour des règles TVA: {str(e)}"
        )

@app.put("/tva-rules/{type}", tags=["TVA"], dependencies=[Depends(verify_api_key)])
async def update_tva_rule(type: str, rule: TVARule):
    """
    Met à jour une règle TVA spécifique
    
    - type: Type de TVA (standard, intermédiaire, réduit, etc.)
    - rule: Nouvelle règle à appliquer
    """
    try:
        # Charger les règles TVA existantes
        with open('tva_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        # Vérifier que le type de TVA existe
        if type not in rules["tva_rates"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Type de TVA '{type}' non trouvé"
            )
        
        # Mettre à jour la règle
        rules["tva_rates"][type] = rule.rate
        rules["keywords"][type] = rule.keywords
        
        # Sauvegarder les règles TVA
        with open('tva_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "message": f"Règle TVA '{type}' mise à jour avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de la règle TVA: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour de la règle TVA: {str(e)}"
        )

@app.post("/tva-rules/{type}", tags=["TVA"], dependencies=[Depends(verify_api_key)])
async def create_tva_rule(type: str, rule: TVARule):
    """
    Crée une nouvelle règle TVA
    
    - type: Type de TVA (standard, intermédiaire, réduit, etc.)
    - rule: Nouvelle règle à créer
    """
    try:
        # Charger les règles TVA existantes
        with open('tva_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        # Vérifier que le type de TVA n'existe pas déjà
        if type in rules["tva_rates"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Type de TVA '{type}' existe déjà"
            )
        
        # Ajouter la nouvelle règle
        rules["tva_rates"][type] = rule.rate
        rules["keywords"][type] = rule.keywords
        
        # Sauvegarder les règles TVA
        with open('tva_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "message": f"Règle TVA '{type}' créée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création de la règle TVA: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de la règle TVA: {str(e)}"
        )

@app.delete("/tva-rules/{type}", tags=["TVA"], dependencies=[Depends(verify_api_key)])
async def delete_tva_rule(type: str):
    """
    Supprime une règle TVA
    
    - type: Type de TVA à supprimer
    """
    try:
        # Charger les règles TVA existantes
        with open('tva_rules.json', 'r', encoding='utf-8') as f:
            rules = json.load(f)
        
        # Vérifier que le type de TVA existe
        if type not in rules["tva_rates"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Type de TVA '{type}' non trouvé"
            )
        
        # Supprimer la règle
        del rules["tva_rates"][type]
        del rules["keywords"][type]
        
        # Sauvegarder les règles TVA
        with open('tva_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        
        return {"status": "success", "message": f"Règle TVA '{type}' supprimée avec succès"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la suppression de la règle TVA: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression de la règle TVA: {str(e)}"
        )

# Point d'entrée pour exécuter l'API
if __name__ == "__main__":
    uvicorn.run("ca_api:app", host="0.0.0.0", port=8000, reload=True) 