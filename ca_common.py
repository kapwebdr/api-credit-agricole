import os
import sys
import datetime
from dotenv import load_dotenv
from urllib import parse
import requests
import json

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
    

class Authentificate:
    def __init__(self, username, password, region):
        """authenticator class"""
        self.url = "https://www.credit-agricole.fr"
        self.ssl_verify = True
        self.username = username
        self.password = password
        self.cookies = None
        self.region = region
        
        self.authenticate()
        
    def map_digit(self, key_layout, digit):
        """map digit with key layout"""
        i = 0
        for k in key_layout:
            if int(digit) == int(k):
                return i
            i += 1
            
    def authenticate(self):
        """authenticate user"""
        # get the keypad layout for the password
        url = f"{self.url}/ca-{self.region}/particulier/"
        url += "acceder-a-mes-comptes.authenticationKeypad.json"
        r = requests.post(url=url,
                          verify=self.ssl_verify)
        if r.status_code != 200:
            raise Exception( "[error] keypad: %s - %s" % (r.status_code, r.text) )

        self.cookies = r.cookies 
        rsp = json.loads(r.text)
        self.keypadId = rsp["keypadId"]
        
        # compute the password according to the layout
        j_password = []
        for d in self.password:
            k = self.map_digit(key_layout=rsp["keyLayout"], digit=d)
            j_password.append( "%s" % k)

        # authenticate the user
        url = f"{self.url}/ca-{self.region}/particulier/"
        url += "acceder-a-mes-comptes.html/j_security_check"
        headers={'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
        payload = {'j_password': ",".join(j_password),
                   'path': '/content/npc/start',
                   'j_path_ressource': f'%2Fca-{self.region}%2Fparticulier%2Foperations%2Fsynthese.html',
                   'j_username': self.username,
                   'keypadId': rsp["keypadId"],
                   'j_validate': "true"}
        r2 = requests.post(url=url,
                          data=parse.urlencode(payload),
                          headers=headers,
                          verify=self.ssl_verify,
                          cookies = r.cookies)
        if r2.status_code != 200:
            raise Exception( "[error] securitycheck: %s - %s" % (r2.status_code, r2.text) )
        # success, extract cookies and save-it
        self.cookies = requests.cookies.merge_cookies(self.cookies, r2.cookies)
        



class Accounts:
    def __init__(self, session,region):
        """operations class"""
        self.url = "https://www.credit-agricole.fr"
        self.session = session
        self.list = []
        self.region = region
        
    def __iter__(self):
        """iter"""
        self.n = 0
        return self
        
    def __next__(self):
        """next"""
        if self.n < len(self.list):
            op = self.list[self.n]
            self.n += 1
            return op
        else:
            raise StopIteration
    
    def process(self,account_number, date_start, date_end, dynamic_dir, file_extension):
        """Traite un compte spécifique et télécharge ses opérations"""
        print(f"\n--- Traitement du compte {account_number} ---")
        
        try:
            # Définir les chemins de sortie avec le numéro de compte comme nom de fichier
            operations_file = os.path.join(dynamic_dir, f"{account_number}.{file_extension}")
            
            print(f"Téléchargement des opérations vers {operations_file}")

            # Téléchargement
            self.download_operations_file(
                account_number=account_number,
                format=file_extension, 
                output_path=operations_file,
                date_start=date_start,
                date_stop=date_end
            )
            
            print(f"Opérations téléchargées avec succès dans {operations_file}")
            print(f"Pour traiter ce fichier, utilisez: python process_ca_pdf.py --input {operations_file} --output {dynamic_dir}")
            return True
        except Exception as e:
            print(f"Erreur lors du traitement du compte {account_number}: {e}")
            return False
             
    def download_operations_file(self, account_number, format="xlsx", output_path=None, date_start=None, date_stop=None):
        """Télécharge les opérations via l'API d'export du CA
        
        Args:
            format (str): Format d'export ('xlsx', 'csv', 'pdf', etc.)
            output_path (str): Chemin où sauvegarder le fichier
            date_start (str): Date de début au format 'DD/MM/YYYY'
            date_stop (str): Date de fin au format 'DD/MM/YYYY'
        """
        # Construire l'URL basée sur le département (caisse régionale)
        # URL exacte observée dans votre XHR
        download_url = f"{self.session.url}/ca-"+self.region+"/professionnel/operations/operations-courantes/telechargement/jcr:content.telechargementServlet.json"
        
        # Construction du payload selon le format observé
        payload = {
            "comptes": [
                account_number
            ],
            "format": format,
            "debut": date_start,  # Format attendu: "DD/MM/YYYY"
            "fin": date_stop,     # Format attendu: "DD/MM/YYYY"
            "type": "m",          # m = mensuel? à confirmer
            "dateDebutList": {
                account_number: date_start
            }
        }
        print(f"Téléchargement depuis {download_url}")
        print(f"Paramètres: {payload}")
        
        # Utiliser la session existante qui contient déjà l'authentification
        response = requests.post(
            url=download_url,
            json=payload,
            cookies=self.session.cookies,
            verify=self.session.ssl_verify
        )
        
        if response.status_code != 200:
            raise Exception(f"Échec du téléchargement: {response.status_code} - {response.text[:100]}")
        
        # Sauvegarder ou retourner le contenu
        if output_path:
            # Créer le répertoire parent si nécessaire
            parent_dir = os.path.dirname(output_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path
        else:
            return response.content