"""
module_veille/veille_agent.py
Veille web en temps reel via Tavily API.
Pipeline : question -> recherche Tavily -> synthese LLM -> reponse structuree
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from groq import Groq

BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE)

logger    = logging.getLogger(__name__)
GROQ_MODEL = "llama-3.3-70b-versatile"


# ──────────────────────────────────────────
# CLIENT TAVILY
# ──────────────────────────────────────────
def get_tavily_client():
    """
    Retourne le client Tavily.
    Leve une erreur claire si la cle API est absente.
    """
    try:
        from tavily import TavilyClient
    except ImportError:
        raise ImportError(
            "Le package 'tavily-python' n'est pas installe. "
            "Lancez : pip install tavily-python"
        )

    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY absent du fichier .env. "
            "Obtenez une cle gratuite sur https://app.tavily.com"
        )
    from tavily import TavilyClient
    return TavilyClient(api_key=api_key)


# ──────────────────────────────────────────
# RECHERCHE
# ──────────────────────────────────────────
def rechercher(
    query: str,
    nb_resultats: int = 5,
    profondeur: str = "basic",
) -> list[dict]:
    """
    Lance une recherche Tavily et retourne les resultats bruts.

    Parametres :
        query        : la requete de recherche
        nb_resultats : nombre de resultats (1-10)
        profondeur   : "basic" (rapide) ou "advanced" (plus complet, consomme plus de credits)

    Retourne une liste de dicts :
        [{"title": ..., "url": ..., "content": ..., "score": ...}, ...]
    """
    client = get_tavily_client()

    response = client.search(
        query=query,
        search_depth=profondeur,
        max_results=nb_resultats,
        include_answer=False,
        include_raw_content=False,
    )

    resultats = []
    for r in response.get("results", []):
        resultats.append({
            "titre":   r.get("title", "Sans titre"),
            "url":     r.get("url", ""),
            "contenu": r.get("content", ""),
            "score":   round(r.get("score", 0.0), 3),
        })

    return resultats


# ──────────────────────────────────────────
# SYNTHESE LLM
# ──────────────────────────────────────────
PROMPT_SYNTHESE = """Tu es un analyste de veille strategique pour une entreprise.
Date du jour : {date}

A partir des resultats de recherche suivants, reponds a la question posee.

QUESTION : {question}

RESULTATS DE RECHERCHE :
{resultats}

INSTRUCTIONS :
- Synthetise les informations cles en reponse directe a la question.
- Structure ta reponse avec des points clairs si necesaire.
- Cite les sources entre [crochets] apres chaque information importante.
- Si les resultats sont insuffisants, dis-le clairement.
- Termine par une section "Points d'attention" si tu identifies des elements critiques.
- Reponds en francais."""


def formater_resultats(resultats: list[dict]) -> str:
    lignes = []
    for i, r in enumerate(resultats, 1):
        lignes.append(
            f"[{i}] {r['titre']}\n"
            f"    URL : {r['url']}\n"
            f"    {r['contenu'][:600]}"
        )
    return "\n\n".join(lignes)


def synthetiser(question: str, resultats: list[dict]) -> str:
    """Synthetise les resultats de recherche via le LLM."""
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    resultats_formates = formater_resultats(resultats)
    date_str           = datetime.now().strftime("%d/%m/%Y")

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{
            "role": "user",
            "content": PROMPT_SYNTHESE.format(
                date=date_str,
                question=question,
                resultats=resultats_formates,
            )
        }],
        temperature=0.3,
        max_tokens=1500,
    )
    return response.choices[0].message.content.strip()


# ──────────────────────────────────────────
# REFORMULATION DE LA REQUETE
# ──────────────────────────────────────────
PROMPT_REQUETE = """Tu es un expert en recherche web.
Transforme cette question en une requete de recherche optimisee pour un moteur de recherche.
Reponds UNIQUEMENT avec la requete, sans explication, sans guillemets.

Question : {question}
Requete optimisee :"""


def optimiser_requete(question: str) -> str:
    """
    Reformule la question en requete de recherche optimisee.
    Ex : "quelles sont les tendances IA en 2025 ?" -> "tendances intelligence artificielle 2025"
    """
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": PROMPT_REQUETE.format(question=question)
            }],
            temperature=0.1,
            max_tokens=80,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.warning("Optimisation requete echouee (%s). Utilisation question brute.", e)
        return question


# ──────────────────────────────────────────
# PIPELINE COMPLET
# ──────────────────────────────────────────
def recherche_et_synthese(
    question: str,
    nb_resultats: int = 5,
    optimiser: bool = True,
) -> dict:
    """
    Pipeline complet de veille web.

    Retourne :
    {
        "reponse":   str,           # synthese LLM
        "sources":   list[dict],    # resultats bruts
        "requete":   str,           # requete utilisee
        "nb_sources": int
    }
    """
    # 1. Optimiser la requete si demande
    requete = optimiser_requete(question) if optimiser else question
    logger.info("Requete veille : %s", requete)

    # 2. Rechercher
    resultats = rechercher(requete, nb_resultats=nb_resultats)

    if not resultats:
        return {
            "reponse":    "Aucun resultat trouve pour cette recherche.",
            "sources":    [],
            "requete":    requete,
            "nb_sources": 0,
        }

    # 3. Synthetiser
    reponse = synthetiser(question, resultats)

    return {
        "reponse":    reponse,
        "sources":    resultats,
        "requete":    requete,
        "nb_sources": len(resultats),
    }

