"""
docs/database.py
Pipeline Text-to-SQL + detection automatique de graphiques Plotly.
"""

import os
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from groq import Groq

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
DB_PATH  = BASE_DIR / "entreprise.db"

load_dotenv(dotenv_path=ENV_FILE)
logger = logging.getLogger(__name__)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
client = Groq(api_key=os.environ["GROQ_API_KEY"])

GROQ_MODEL = "llama-3.3-70b-versatile"

DB_SCHEMA = """
Tables disponibles :
employes(id, nom, prenom, poste, departement, salaire, date_embauche)
produits(id, nom, categorie, prix, stock)
clients(id, nom, email, ville, pays)
ventes(id, produit_id, montant, quantite, date_vente, client_id, vendeur_id)

Relations :
  ventes.vendeur_id -> employes.id
  ventes.client_id  -> clients.id
  ventes.produit_id -> produits.id
"""

SQL_PROMPT = """Tu es un expert SQL sur SQLite.
Schema : {schema}
Genere UNIQUEMENT la requete SQL brute, sans markdown, sans commentaires.
Question : {question}
SQL :"""

REPONSE_PROMPT = """Tu es un assistant d'entreprise.
Question : {question}
Resultats :
{resultats}
Formule une reponse claire et concise en francais. Si vide, explique pourquoi."""

GRAPH_PROMPT = """Analyse ces resultats SQL et dis si un graphique est pertinent.
Reponds UNIQUEMENT en JSON valide :
{{
  "graphique": true/false,
  "type": "bar" | "line" | "pie" | null,
  "colonne_x": "nom_colonne_ou_null",
  "colonne_y": "nom_colonne_ou_null",
  "titre": "titre court du graphique"
}}

Regles :
- bar   : comparaison de categories (ventes par produit, salaires par departement)
- line  : evolution dans le temps (ventes par mois)
- pie   : repartition en pourcentage (max 8 elements)
- false : si une seule valeur, ou donnees non chiffrables

Colonnes disponibles : {colonnes}
Extrait des donnees : {extrait}
Question originale : {question}"""


def generate_sql(question: str) -> str:
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": SQL_PROMPT.format(schema=DB_SCHEMA, question=question)}],
        temperature=0.1,
    )
    return response.choices[0].message.content.strip().replace("```sql", "").replace("```", "").strip()


def execute_sql(sql: str):
    with engine.connect() as conn:
        result  = conn.execute(text(sql))
        rows    = result.fetchall()
        columns = list(result.keys())
    return columns, rows


def format_results(columns: list, rows: list) -> str:
    if not rows:
        return "Aucun resultat."
    header = " | ".join(columns)
    lines  = [header, "-" * max(len(header), 40)]
    for row in rows:
        lines.append(" | ".join(str(v) for v in row))
    return "\n".join(lines)


def detecter_graphique(question: str, columns: list, rows: list) -> dict:
    """Demande au LLM si un graphique est pertinent et lequel."""
    if not rows or len(rows) < 2 or len(columns) < 2:
        return {"graphique": False}
    try:
        extrait = str([dict(zip(columns, r)) for r in rows[:5]])
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": GRAPH_PROMPT.format(
                colonnes=columns,
                extrait=extrait,
                question=question,
            )}],
            temperature=0.1,
        )
        text_r = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        return json.loads(text_r)
    except Exception as e:
        logger.warning("Detection graphique echouee : %s", e)
        return {"graphique": False}


def construire_graphique(graph_info: dict, columns: list, rows: list):
    """
    Construit un graphique Plotly depuis les resultats SQL.
    Retourne une figure Plotly ou None.
    """
    try:
        import plotly.graph_objects as go

        col_x = graph_info.get("colonne_x")
        col_y = graph_info.get("colonne_y")
        titre = graph_info.get("titre", "Resultats")
        type_g = graph_info.get("type", "bar")

        if col_x not in columns or col_y not in columns:
            return None

        idx_x = columns.index(col_x)
        idx_y = columns.index(col_y)
        x_vals = [str(r[idx_x]) for r in rows]
        y_vals = [r[idx_y] for r in rows]

        # Convertir en float si possible
        try:
            y_vals = [float(v) if v is not None else 0 for v in y_vals]
        except (ValueError, TypeError):
            return None

        layout = go.Layout(
            title=dict(text=titre, font=dict(size=14)),
            margin=dict(l=40, r=20, t=40, b=60),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(size=12),
            xaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
            yaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
        )

        if type_g == "bar":
            fig = go.Figure(
                data=[go.Bar(x=x_vals, y=y_vals, marker_color="#4f86f7")],
                layout=layout,
            )
        elif type_g == "line":
            fig = go.Figure(
                data=[go.Scatter(x=x_vals, y=y_vals, mode="lines+markers", line=dict(color="#4f86f7"))],
                layout=layout,
            )
        elif type_g == "pie":
            fig = go.Figure(
                data=[go.Pie(labels=x_vals, values=y_vals, hole=0.3)],
                layout=go.Layout(
                    title=dict(text=titre, font=dict(size=14)),
                    margin=dict(l=20, r=20, t=40, b=20),
                    height=320,
                    paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(size=12),
                ),
            )
        else:
            return None

        return fig

    except Exception as e:
        logger.warning("Construction graphique echouee : %s", e)
        return None


def answer_question(question: str) -> dict:
    """
    Pipeline complet : question -> SQL -> resultats -> reponse + graphique optionnel.

    Retourne :
    {
        "reponse": str,
        "figure":  plotly.Figure | None,
        "sql":     str,
    }
    """
    logger.info("Question BDD : %s", question)

    sql = generate_sql(question)
    logger.info("SQL : %s", sql)

    try:
        columns, rows = execute_sql(sql)
        resultats_txt = format_results(columns, rows)
    except Exception as e:
        return {
            "reponse": f"Erreur SQL : {e}\nRequete tentee : {sql}",
            "figure":  None,
            "sql":     sql,
        }

    # Reponse textuelle
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": REPONSE_PROMPT.format(
            question=question,
            resultats=resultats_txt,
        )}],
        temperature=0.3,
    )
    reponse_txt = response.choices[0].message.content.strip()

    # Graphique
    figure = None
    graph_info = detecter_graphique(question, columns, rows)
    if graph_info.get("graphique"):
        figure = construire_graphique(graph_info, columns, rows)

    return {
        "reponse": reponse_txt,
        "figure":  figure,
        "sql":     sql,
    }


if __name__ == "__main__":
    print("Agent BDD pret.\n")
    while True:
        q = input("Question : ").strip()
        if q.lower() in ("q", "quitter"):
            break
        if not q:
            continue
        result = answer_question(q)
        print(f"\nReponse : {result['reponse']}")
        if result["figure"]:
            print("(graphique disponible dans Streamlit)")
        print("-" * 60)

