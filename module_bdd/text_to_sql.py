import os
import re
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from db_connector import get_schema

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")
client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM_SQL = """Tu es un expert SQL specialise en SQLite.
Convertis la question en requete SQL valide.
Regles :
- Retourne UNIQUEMENT la requete SQL, rien d'autre
- Pas de markdown, pas de commentaires
- Utilise des alias lisibles (COUNT(*) AS total)
- Pour noms complets : prenom || ' ' || nom AS nom_complet
- Jointures via les cles etrangeres du schema

Schema :
{schema}
"""

SYSTEM_ANALYSE = """Tu es un analyste business senior qui conseille la direction d'une entreprise.
Tu recois des donnees issues d'une base de donnees et tu dois :
1. Formuler une reponse claire et directe a la question posee
2. Analyser les donnees en profondeur (tendances, ecarts, points notables)
3. Identifier les points forts et les points d'attention
4. Formuler 2 ou 3 recommandations concretes et actionnables

Style :
- Ton professionnel et structure
- Utilise des chiffres precis issus des donnees
- Commence par repondre directement a la question
- Ensuite l'analyse
- Termine par les recommandations
- Si aucune donnee n'est disponible, explique pourquoi et propose une alternative
"""

def nettoyer_sql(sql: str) -> str:
    sql = re.sub(r'```sql|```', '', sql)
    sql = re.sub(r'^\s*sql\s*', '', sql, flags=re.IGNORECASE)
    return sql.strip().rstrip(';') + ';'

def question_vers_sql(question: str) -> str:
    schema   = get_schema()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_SQL.format(schema=schema)},
            {"role": "user",   "content": f"Question : {question}"}
        ],
        temperature=0.1
    )
    return nettoyer_sql(response.choices[0].message.content.strip())

def sql_vers_analyse(question: str, resultats_bruts: str, nb_lignes: int) -> str:
    contexte = f"""Question posee : {question}

Nombre de resultats : {nb_lignes} ligne(s)

Donnees :
{resultats_bruts}
"""
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_ANALYSE},
            {"role": "user",   "content": contexte}
        ],
        temperature=0.4
    )
    return response.choices[0].message.content.strip()