from creditagricole_particuliers import Authenticator, Accounts
from creditagricole_particuliers.accounts import Account
import requests
import os
import sys
from types import MethodType
import argparse
import ca_common

class EnhancedAccount(Account):
    def download_operations_file(self, format="xlsx", output_path=None, date_start=None, date_stop=None):
        """Télécharge les opérations via l'API d'export du CA
        
        Args:
            format (str): Format d'export ('xlsx', 'csv', 'pdf', etc.)
            output_path (str): Chemin où sauvegarder le fichier
            date_start (str): Date de début au format 'DD/MM/YYYY'
            date_stop (str): Date de fin au format 'DD/MM/YYYY'
        """
        # Construire l'URL basée sur le département (caisse régionale)
        # URL exacte observée dans votre XHR
        download_url = f"{self.session.url}/{self.session.regional_bank_url}/professionnel/operations/operations-courantes/telechargement/jcr:content.telechargementServlet.json"
        
        # Construction du payload selon le format observé
        payload = {
            "comptes": [
                self.numeroCompte
            ],
            "format": format,
            "debut": date_start,  # Format attendu: "DD/MM/YYYY"
            "fin": date_stop,     # Format attendu: "DD/MM/YYYY"
            "type": "m",          # m = mensuel? à confirmer
            "dateDebutList": {
                self.numeroCompte: date_start
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

def patch_account_search():
    """Patch pour améliorer la classe Account avec notre version étendue"""
    original_search = Accounts.search

    def enhanced_search(self, *args, **kwargs):
        account = original_search(self, *args, **kwargs)
        # Créer un nouvel objet avec les mêmes attributs
        enhanced = EnhancedAccount(session=account.session, account=account.account)
        return enhanced

    Accounts.search = enhanced_search

def process_account(account_number, session, date_start, date_end, dynamic_dir, file_extension):
    """Traite un compte spécifique et télécharge ses opérations"""
    print(f"\n--- Traitement du compte {account_number} ---")
    
    try:
        account = Accounts(session=session).search(num=account_number)
        
        # Définir les chemins de sortie avec le numéro de compte comme nom de fichier
        operations_file = os.path.join(dynamic_dir, f"{account_number}.{file_extension}")
        
        print(f"Téléchargement des opérations vers {operations_file}")

        # Téléchargement
        account.download_operations_file(
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

def main():
    # Analyse des arguments en ligne de commande
    parser = argparse.ArgumentParser(description="Télécharge les relevés de compte du Crédit Agricole")
    parser.add_argument("--env", help="Chemin vers un fichier .env alternatif")
    parser.add_argument("--account", help="Numéro de compte spécifique à traiter (si non spécifié, tous les comptes sont traités)")
    args = parser.parse_args()
    
    # Charger le fichier .env approprié
    ca_common.load_environment(args.env)
    
    # Patchez la méthode search
    patch_account_search()
    
    # Récupération des informations d'authentification depuis .env
    username = os.getenv('CA_USERNAME')
    password_str = os.getenv('CA_PASSWORD')
    department = int(os.getenv('CA_DEPARTMENT'))
    
    if not all([username, password_str, department]):
        print("Erreur: Informations d'authentification incomplètes dans le fichier .env")
        sys.exit(1)
    
    # Récupération des numéros de compte et extension du fichier
    file_extension = ca_common.get_file_extension()
    
    # Conversion du mot de passe en liste d'entiers
    password = [int(digit) for digit in password_str] if password_str else []
    
    # Récupération de la liste des comptes et filtrage si nécessaire
    all_accounts = ca_common.get_account_numbers()
    
    # Filtrer les comptes si un compte spécifique est demandé
    if args.account:
        if args.account not in all_accounts:
            print(f"Erreur: Le compte {args.account} n'est pas dans la liste des comptes configurés.")
            sys.exit(1)
        accounts = [args.account]
    else:
        accounts = all_accounts
    
    # Dates du mois précédent
    dates = ca_common.get_previous_month_dates()
    date_start = dates["date_start"]
    date_end = dates["date_end"]
    
    # Obtention du répertoire dynamique
    dynamic_dir = ca_common.get_dynamic_directory()
    
    print(f"Période: {date_start} - {date_end}")
    print(f"Répertoire de destination: {dynamic_dir}")
    print(f"Nombre de comptes à traiter: {len(accounts)}")
    
    # Créer la session une seule fois pour tous les comptes
    try:
        session = Authenticator(username=username, password=password, department=department)
        print("Authentification réussie")
    except Exception as e:
        print(f"Erreur d'authentification: {e}")
        sys.exit(1)
    
    # Traiter chaque compte
    success_count = 0
    for account_number in accounts:
        if process_account(account_number, session, date_start, date_end, dynamic_dir, file_extension):
            success_count += 1
    
    print(f"\nTraitement terminé: {success_count}/{len(accounts)} comptes traités avec succès")
    
    if success_count == 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()