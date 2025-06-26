import os
import sys
from types import MethodType
import argparse
import ca_common


def main():
    # Analyse des arguments en ligne de commande
    parser = argparse.ArgumentParser(description="Télécharge les relevés de compte du Crédit Agricole")
    parser.add_argument("--env", help="Chemin vers un fichier .env alternatif")
    parser.add_argument("--account", help="Numéro de compte spécifique à traiter (si non spécifié, tous les comptes sont traités)")
    parser.add_argument("--start-date", help="Date de début au format DD/MM/YYYY (si non spécifiée, début du mois précédent)")
    parser.add_argument("--end-date", help="Date de fin au format DD/MM/YYYY (si non spécifiée, fin du mois précédent)")
    parser.add_argument("--force", action="store_true", help="Force le téléchargement même si le fichier existe déjà")
    args = parser.parse_args()
    
    # Charger le fichier .env approprié
    ca_common.load_environment(args.env)
    
    # Récupération des informations d'authentification depuis .env
    username = os.getenv('CA_USERNAME')
    password_str = os.getenv('CA_PASSWORD')
    region = os.getenv('CA_REGION')
    
    if not all([username, password_str, region]):
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
    
    # Obtenir les dates (utiliser celles fournies en paramètre si présentes)
    if args.start_date and args.end_date:
        date_start = args.start_date
        date_end = args.end_date
        print(f"Utilisation des dates fournies: {date_start} - {date_end}")
    elif args.start_date:
        date_start = args.start_date
        # Si seulement la date de début est fournie, utiliser la date de fin par défaut
        dates = ca_common.get_previous_month_dates()
        date_end = dates["date_end"]
        print(f"Utilisation de la date de début fournie et date de fin par défaut: {date_start} - {date_end}")
    elif args.end_date:
        date_end = args.end_date
        # Si seulement la date de fin est fournie, utiliser la date de début par défaut
        dates = ca_common.get_previous_month_dates()
        date_start = dates["date_start"]
        print(f"Utilisation de la date de fin fournie et date de début par défaut: {date_start} - {date_end}")
    else:
        # Dates du mois précédent par défaut
        dates = ca_common.get_previous_month_dates()
        date_start = dates["date_start"]
        date_end = dates["date_end"]
        print(f"Utilisation des dates par défaut: {date_start} - {date_end}")
    
    # Obtention du répertoire dynamique
    dynamic_dir = ca_common.get_dynamic_directory()
    
    print(f"Période: {date_start} - {date_end}")
    print(f"Répertoire de destination: {dynamic_dir}")
    print(f"Nombre de comptes à traiter: {len(accounts)}")
    
    # Créer la session une seule fois pour tous les comptes
    try:
        session = ca_common.Authentificate(username=username, password=password, region=region)
        print("Authentification réussie")
    except Exception as e:
        print(f"Erreur d'authentification: {e}")
        sys.exit(1)
    # Traiter chaque compte
    success_count = 0
    for account_number in accounts:
        # Vérifier si le fichier existe déjà et si on ne force pas le téléchargement
        output_file = os.path.join(dynamic_dir, f"{account_number}.{file_extension}")
        if os.path.exists(output_file) and not args.force:
            print(f"\n--- Compte {account_number}: fichier déjà présent, ignoré (utilisez --force pour forcer) ---")
            continue
            
        # Traiter le compte
        ca_accounts = ca_common.Accounts(session,region)
        if ca_accounts.process(account_number,date_start, date_end, dynamic_dir, file_extension):
            success_count += 1
    
    print(f"\nTraitement terminé: {success_count}/{len(accounts)} comptes traités avec succès")
    
    if success_count == 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()