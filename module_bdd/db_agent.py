import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from db_connector import executer_sql, formater_resultats, get_stats, lister_tables
from text_to_sql  import question_vers_sql, sql_vers_analyse

def repondre(question: str) -> dict:
    try:
        sql            = question_vers_sql(question)
        columns, rows  = executer_sql(sql)
        resultats_bruts = formater_resultats(columns, rows)
        analyse        = sql_vers_analyse(question, resultats_bruts, len(rows))
        return {
            "succes":   True,
            "question": question,
            "sql":      sql,
            "colonnes": columns,
            "lignes":   rows,
            "brut":     resultats_bruts,
            "reponse":  analyse
        }
    except Exception as e:
        return {
            "succes":   False,
            "question": question,
            "erreur":   str(e),
            "reponse":  f"Erreur : {e}"
        }

def afficher_stats():
    stats = get_stats()
    print("\nBase de donnees :")
    for table, count in stats.items():
        print(f"  {table:<20} {count} enregistrement(s)")