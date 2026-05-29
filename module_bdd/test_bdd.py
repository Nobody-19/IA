import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from create_db    import creer_base
from db_agent     import repondre, afficher_stats
from db_connector import importer_csv, importer_excel, lister_tables

def menu_import():
    print("\n--- IMPORT DE DONNEES ---")
    print("  [1] Importer un fichier CSV")
    print("  [2] Importer un fichier Excel (.xlsx)")
    print("  [0] Retour")
    choix = input("Choix : ").strip()

    if choix == "1":
        chemin = input("Chemin du fichier CSV : ").strip().strip('"')
        table  = input("Nom de la table a creer : ").strip()
        sep    = input("Separateur (Entree pour virgule) : ").strip() or ","
        res    = importer_csv(chemin, table, sep)
        if res["succes"]:
            print(f"\nOK : {res['lignes']} lignes importees dans '{res['table']}'")
            print(f"Colonnes : {', '.join(res['colonnes'])}")
        else:
            print(f"\nErreur : {res['erreur']}")

    elif choix == "2":
        chemin = input("Chemin du fichier Excel : ").strip().strip('"')
        table  = input("Nom de la table a creer : ").strip()
        res    = importer_excel(chemin, table)
        if res["succes"]:
            print(f"\nOK : {res['lignes']} lignes importees dans '{res['table']}'")
            print(f"Colonnes : {', '.join(res['colonnes'])}")
        else:
            print(f"\nErreur : {res['erreur']}")

def main():
    print("Initialisation...")
    creer_base()
    afficher_stats()

    print("\n" + "="*60)
    print("  Agent BDD — Analyse & Recommandations")
    print("  Commandes speciales :")
    print("  'import'   pour charger tes propres donnees")
    print("  'tables'   pour voir les tables disponibles")
    print("  'stats'    pour voir les stats de la base")
    print("  'quitter'  pour arreter")
    print("="*60 + "\n")

    while True:
        question = input("Ta question : ").strip()

        if not question:
            continue

        if question.lower() == "quitter":
            print("Au revoir !")
            break

        if question.lower() == "import":
            menu_import()
            afficher_stats()
            continue

        if question.lower() == "tables":
            tables = lister_tables()
            print("\nTables disponibles :")
            for t in tables:
                print(f"  > {t}")
            continue

        if question.lower() == "stats":
            afficher_stats()
            continue

        resultat = repondre(question)
        if resultat["succes"]:
            print(f"\nSQL genere : {resultat['sql']}")
            print(f"\n{resultat['reponse']}\n")
        else:
            print(f"\nErreur : {resultat['erreur']}\n")
        print("-"*60)

if __name__ == "__main__":
    main()