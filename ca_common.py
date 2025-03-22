import os
import sys
import datetime
from dotenv import load_dotenv

def load_environment(env_path=None):
    """Charge le fichier .env approprié"""
    if env_path:
        if not os.path.exists(env_path):
            print(f"Erreur: Le fichier .env spécifié '{env_path}' n'existe pas.")
            sys.exit(1)
        print(f"Utilisation du fichier .env: {env_path}")
        load_dotenv(env_path)
    else:
        load_dotenv()
        print("Utilisation du fichier .env par défaut")

def get_previous_month_dates():
    """Calcule les dates du mois précédent"""
    today = datetime.datetime.now()
    first_day = datetime.datetime(today.year, today.month, 1)
    
    if today.month == 1:
        last_month = datetime.datetime(today.year - 1, 12, 1)
        last_month_year = today.year - 1
        last_month_month = 12
    else:
        last_month = datetime.datetime(today.year, today.month - 1, 1)
        last_month_year = today.year
        last_month_month = today.month - 1
    
    date_start = last_month.strftime("%d/%m/%Y")
    date_end = (first_day - datetime.timedelta(days=1)).strftime("%d/%m/%Y")
    
    return {
        "date_start": date_start,
        "date_end": date_end,
        "year": last_month_year,
        "month": last_month_month
    }

def get_dynamic_directory():
    """Obtient le répertoire dynamique basé sur l'année et le mois précédent"""
    dates = get_previous_month_dates()
    
    # Création du chemin dynamique
    base_path = os.getenv('CA_BASE_PATH', '')
    
    # Format du chemin dynamique: BASE_PATH/ANNÉE/MOIS
    year_month_dir = f"{dates['year']}/{dates['month']:02d}"
    dynamic_dir = os.path.join(base_path, year_month_dir)
    
    # Créer le répertoire si nécessaire
    os.makedirs(dynamic_dir, exist_ok=True)
    
    return dynamic_dir

def get_account_numbers():
    """Récupère la liste des numéros de compte depuis le fichier .env"""
    accounts_str = os.getenv('CA_ACCOUNT_NUMBERS')
    
    if not accounts_str:
        print("Erreur: Aucun numéro de compte trouvé dans le fichier .env (CA_ACCOUNT_NUMBERS)")
        sys.exit(1)
    
    # Conversion de la chaîne de comptes en liste
    return [acc.strip() for acc in accounts_str.split(',') if acc.strip()]

def get_file_extension():
    """Récupère l'extension de fichier depuis le fichier .env"""
    return os.getenv('CA_FILE_EXTENSION', 'xlsx')

def get_account_files(directory=None, account_number=None, extension=None):
    """
    Trouve les fichiers de compte dans le répertoire spécifié.
    
    Args:
        directory: Le répertoire à analyser (par défaut: le répertoire dynamique du mois précédent)
        account_number: Un numéro de compte spécifique à rechercher (par défaut: tous les comptes)
        extension: L'extension de fichier à rechercher (par défaut: depuis .env)
    
    Returns:
        Une liste de tuples (chemin_fichier, numéro_compte)
    """
    if directory is None:
        directory = get_dynamic_directory()
    
    if extension is None:
        extension = get_file_extension()
    
    if account_number:
        # Chercher un fichier pour un compte spécifique
        filepath = os.path.join(directory, f"{account_number}.{extension}")
        if os.path.exists(filepath):
            return [(filepath, account_number)]
        else:
            print(f"Aucun fichier trouvé pour le compte {account_number} dans {directory}")
            return []
    else:
        # Chercher tous les fichiers correspondant au pattern [NUMERO_COMPTE].[EXTENSION]
        all_accounts = get_account_numbers()
        result = []
        
        for acc in all_accounts:
            filepath = os.path.join(directory, f"{acc}.{extension}")
            if os.path.exists(filepath):
                result.append((filepath, acc))
        
        return result 