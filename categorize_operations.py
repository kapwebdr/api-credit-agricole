import pandas as pd
import os
from dotenv import load_dotenv
import json
import pathlib

# Chargement des variables d'environnement
load_dotenv()

# Configuration des taux de TVA et catégories
TVA_RATES = {
    "standard": 20.0,
    "intermédiaire": 10.0,
    "réduit": 5.5,
    "particulier": 7.0,
    "exonéré": 0.0
}

# Définition des catégories de dépenses (à personnaliser)
EXPENSE_CATEGORIES = [
    "Fournitures Bureau",
    "Matériel Informatique",
    "Services Pro",
    "Déplacements",
    "Repas Pro",
    "Télécom",
    "Logiciels/Abonnements",
    "Formation",
    "Cotisations",
    "Loyer/Immobilier",
    "Publicité/Marketing",
    "Frais Bancaires",
    "Autre"
]

# Définition des catégories de revenus (à personnaliser)
INCOME_CATEGORIES = [
    "Prestation de Services",
    "Vente de Produits",
    "Remboursements",
    "Subventions",
    "Autre"
]

def load_rules_file():
    """Charge le fichier de règles de catégorisation s'il existe, sinon en crée un"""
    rules_file = "categorization_rules.json"
    
    if os.path.exists(rules_file):
        with open(rules_file, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # Créer un fichier de règles vide
        default_rules = {
            "keywords": {
                # Exemples: mots-clés -> [catégorie, taux TVA]
                "amazon": ["Fournitures Bureau", "standard"],
                "restaurant": ["Repas Pro", "intermédiaire"],
                "uber": ["Déplacements", "intermédiaire"],
                "ovh": ["Télécom", "standard"],
                "formation": ["Formation", "exonéré"]
            }
        }
        
        with open(rules_file, "w", encoding="utf-8") as f:
            json.dump(default_rules, f, indent=2, ensure_ascii=False)
        
        return default_rules

def apply_categorization(df, rules, is_credit=False):
    """Applique les règles de catégorisation à un DataFrame"""
    # Ajouter colonnes pour catégorie et taux TVA
    df['Catégorie'] = None
    df['Taux TVA'] = TVA_RATES["standard"]  # Taux par défaut
    df['Type TVA'] = "standard"
    
    # Colonne à utiliser pour la recherche de mots-clés
    description_cols = [col for col in df.columns if any(kw in col.lower() for kw in ['libellé', 'description', 'libelle'])]
    
    if not description_cols:
        print("Aucune colonne de description trouvée.")
        return df
    
    desc_col = description_cols[0]
    
    # Appliquer les règles basées sur les mots-clés
    for keyword, rule in rules["keywords"].items():
        category, tva_type = rule
        mask = df[desc_col].str.lower().str.contains(keyword.lower(), na=False)
        
        if is_credit:
            # Pour les revenus, utiliser les catégories de revenus
            if category in EXPENSE_CATEGORIES:
                # Si la catégorie est une dépense, la changer à "Autre" pour les revenus
                category = "Autre"
        else:
            # Pour les dépenses, utiliser les catégories de dépenses
            if category in INCOME_CATEGORIES:
                # Si la catégorie est un revenu, la changer à "Autre" pour les dépenses
                category = "Autre"
        
        df.loc[mask, 'Catégorie'] = category
        df.loc[mask, 'Taux TVA'] = TVA_RATES[tva_type]
        df.loc[mask, 'Type TVA'] = tva_type
    
    # Assigner une catégorie par défaut aux lignes sans catégorie
    df.loc[df['Catégorie'].isnull(), 'Catégorie'] = "Autre"
    
    return df

def categorize_operations():
    """Catégorise les opérations du fichier Excel exporté du Crédit Agricole"""
    # Récupérer le chemin du fichier d'opérations
    operations_file = os.getenv('CA_DOWNLOAD_PATH')
    output_dir = os.getenv('CA_OUTPUT_DIR', '')
    
    # Charger les règles de catégorisation
    rules = load_rules_file()
    
    try:
        # Lire le fichier Excel
        df = pd.read_excel(operations_file)
        print(f"Fichier lu avec succès: {operations_file}")
        
        # Identifier les colonnes importantes
        date_cols = [col for col in df.columns if 'date' in col.lower()]
        amount_cols = [col for col in df.columns if any(kw in col.lower() for kw in ['montant', 'débit', 'crédit'])]
        
        if not date_cols or not amount_cols:
            print("Colonnes requises non trouvées.")
            return None
        
        date_col = date_cols[0]
        
        # Déterminer la colonne de montant
        if 'Débit' in df.columns and 'Crédit' in df.columns:
            # Créer une colonne de montant unifiée (valeurs négatives pour les débits)
            df['Montant'] = df['Crédit'].fillna(0) - df['Débit'].fillna(0)
            amount_col = 'Montant'
        else:
            amount_col = amount_cols[0]
        
        # Convertir la date
        df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
        
        # Séparer crédits et débits
        credits = df[df[amount_col] > 0].copy()
        debits = df[df[amount_col] < 0].copy()
        debits[amount_col] = debits[amount_col].abs()  # Montants positifs pour les débits
        
        # Appliquer la catégorisation
        credits = apply_categorization(credits, rules, is_credit=True)
        debits = apply_categorization(debits, rules, is_credit=False)
        
        # Recalculer les montants HT et TVA
        for df_op in [credits, debits]:
            df_op['Montant HT'] = df_op[amount_col] / (1 + df_op['Taux TVA'] / 100)
            df_op['TVA'] = df_op[amount_col] - df_op['Montant HT']
        
        # Créer un fichier Excel avec les résultats
        output_file = os.path.join(output_dir, "operations_categorized.xlsx")
        
        with pd.ExcelWriter(output_file) as writer:
            credits.to_excel(writer, sheet_name='Recettes', index=False)
            debits.to_excel(writer, sheet_name='Dépenses', index=False)
            
            # Créer un résumé des dépenses par catégorie
            expense_summary = debits.groupby('Catégorie').agg({
                amount_col: 'sum',
                'Montant HT': 'sum',
                'TVA': 'sum'
            }).reset_index()
            
            expense_summary.columns = ['Catégorie', 'Montant TTC', 'Montant HT', 'TVA']
            expense_summary = expense_summary.sort_values('Montant TTC', ascending=False)
            
            # Ajouter une ligne de total
            expense_summary.loc[len(expense_summary)] = [
                'TOTAL',
                expense_summary['Montant TTC'].sum(),
                expense_summary['Montant HT'].sum(),
                expense_summary['TVA'].sum()
            ]
            
            # Créer un résumé des recettes par catégorie
            income_summary = credits.groupby('Catégorie').agg({
                amount_col: 'sum',
                'Montant HT': 'sum',
                'TVA': 'sum'
            }).reset_index()
            
            income_summary.columns = ['Catégorie', 'Montant TTC', 'Montant HT', 'TVA']
            income_summary = income_summary.sort_values('Montant TTC', ascending=False)
            
            # Ajouter une ligne de total
            income_summary.loc[len(income_summary)] = [
                'TOTAL',
                income_summary['Montant TTC'].sum(),
                income_summary['Montant HT'].sum(),
                income_summary['TVA'].sum()
            ]
            
            # Résumé par taux de TVA
            tva_summary = []
            for tva_type, rate in TVA_RATES.items():
                credits_tva = credits[credits['Type TVA'] == tva_type]['TVA'].sum()
                debits_tva = debits[debits['Type TVA'] == tva_type]['TVA'].sum()
                
                tva_summary.append({
                    'Type TVA': tva_type,
                    'Taux': f"{rate}%",
                    'TVA Collectée': credits_tva,
                    'TVA Déductible': debits_tva,
                    'Solde TVA': credits_tva - debits_tva
                })
            
            tva_df = pd.DataFrame(tva_summary)
            
            # Ajouter un total à la synthèse TVA
            tva_df.loc[len(tva_df)] = [
                'TOTAL', '',
                tva_df['TVA Collectée'].sum(),
                tva_df['TVA Déductible'].sum(),
                tva_df['TVA Collectée'].sum() - tva_df['TVA Déductible'].sum()
            ]
            
            # Écrire les résumés dans le fichier Excel
            expense_summary.to_excel(writer, sheet_name='Résumé Dépenses', index=False)
            income_summary.to_excel(writer, sheet_name='Résumé Recettes', index=False)
            tva_df.to_excel(writer, sheet_name='Synthèse TVA', index=False)
        
        print(f"Catégorisation terminée. Fichier généré: {output_file}")
        return output_file
            
    except Exception as e:
        print(f"Erreur lors du traitement: {e}")
        return None

if __name__ == "__main__":
    categorize_operations() 