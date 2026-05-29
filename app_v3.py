"""
app.py
Interface Streamlit principale de l'agent IA d'entreprise.
Corrections apportees :
  - Indentations sidebar entierement refaites
  - email_programmer sorti du bloc multi et mis dans l'orchestrateur principal
  - Mémoire conversationnelle (CondensePlusContextChatEngine) branchee
  - load_doc centralise dans utils/loader.py
"""

import os
import re
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

import chromadb
import streamlit as st
from dotenv import load_dotenv
from groq import Groq

from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq as GroqLLM

from utils.loader import load_doc, EXTENSIONS_SUPPORTEES
from utils.retriever import construire_retriever
from module_email.scheduler import (
    programmer_email,
    lister_emails_programmes,
    annuler_email_programme,
)
from module_email.priorite import analyser_priorites_batch, badge_priorite
from module_email.gmail_reader import (
    lire_emails as gmail_lire,
    envoyer_email as gmail_envoyer,
    generer_et_envoyer as gmail_generer_envoyer,
)
from module_email.outlook_reader import lire_emails as outlook_lire
from module_email.email_agent import (
    indexer_emails,
    repondre_sur_emails,
    resumer_emails,
    generer_email_professionnel,
)
from docs.database import answer_question as bdd_answer
from utils.historique import (
    nouvelle_conversation, mettre_a_jour_titre, lister_conversations,
    supprimer_conversation, sauvegarder_message, charger_messages,
    compter_messages, generer_titre,
)
from module_veille.veille_agent import recherche_et_synthese as veille_recherche
from docs.rapport import creer_rapport, detecter_type_rapport

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DOCS_DIR     = BASE_DIR / "docs"
CHROMA_DIR   = BASE_DIR / "chroma_db"
ENV_FILE     = BASE_DIR / ".env"
RAPPORTS_DIR = BASE_DIR / "rapports"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_EMAILS = 20

SYSTEM_PROMPT_RAG = """Tu es un assistant expert en analyse de documents d'entreprise.
Regles :
1. Reponds UNIQUEMENT a partir des documents fournis dans le contexte.
2. Cite le nom du fichier source entre [crochets] apres chaque information cle.
3. Si la reponse est absente des documents, dis-le explicitement.
4. Structure ta reponse avec des points clairs si la reponse est longue.
5. Reponds dans la meme langue que la question."""

logging.basicConfig(level=logging.WARNING)
load_dotenv(dotenv_path=ENV_FILE)

st.set_page_config(
    page_title="Agent IA Entreprise",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────
# CSS — Design compatible dark/light mode
# ──────────────────────────────────────────
st.markdown("""
<style>
/* Masquer decorations Streamlit */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }

/* Corriger le label des expanders (bug "arrow_down") */
[data-testid="stSidebar"] details summary p { display: none !important; }
[data-testid="stSidebar"] details summary::after {
    content: attr(data-label);
    font-size: 13px;
    font-weight: 500;
}

/* Boutons sidebar — style neutre */
[data-testid="stSidebar"] .stButton button {
    background: transparent !important;
    border: 0.5px solid rgba(128,128,128,0.3) !important;
    color: inherit !important;
    font-size: 13px !important;
    padding: 5px 10px !important;
    border-radius: 6px !important;
}
[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(128,128,128,0.1) !important;
}
[data-testid="stSidebar"] button[kind="primary"] {
    background: #2563eb !important;
    border-color: #2563eb !important;
    color: #fff !important;
}

/* Topbar badges */
.topbar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 0 14px;
    border-bottom: 1px solid rgba(128,128,128,0.15);
    margin-bottom: 10px;
    flex-wrap: wrap;
}
.tb-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    border: 0.5px solid transparent;
}
.tb-on  { background: rgba(76,175,125,0.15); color: #4caf7d; border-color: rgba(76,175,125,0.3); }
.tb-off { background: rgba(128,128,128,0.08); color: rgba(128,128,128,0.6); border-color: rgba(128,128,128,0.2); }

/* Badges modules dans le chat */
.badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 9px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
    margin-bottom: 6px;
    letter-spacing: 0.02em;
}
.badge-rag     { background: rgba(59,130,246,0.15);  color: #60a5fa; }
.badge-bdd     { background: rgba(34,197,94,0.15);   color: #4ade80; }
.badge-email   { background: rgba(232,121,249,0.15); color: #e879f9; }
.badge-gen     { background: rgba(156,163,175,0.15); color: #9ca3af; }
.badge-multi   { background: rgba(251,146,60,0.15);  color: #fb923c; }
.badge-rapport { background: rgba(167,139,250,0.15); color: #a78bfa; }
.badge-veille  { background: rgba(99,102,241,0.15);  color: #818cf8; }

/* Statut modules sidebar */
.module-row {
    display: flex;
    align-items: center;
    padding: 5px 0;
    font-size: 13px;
    gap: 8px;
}
.dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-on  { background: #4caf7d; }
.dot-off { background: rgba(128,128,128,0.35); }

/* Upload bouton custom */
.upload-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    width: 100%;
    padding: 7px 12px;
    border-radius: 6px;
    border: 0.5px dashed rgba(128,128,128,0.4);
    font-size: 13px;
    cursor: pointer;
    background: transparent;
    color: inherit;
    margin-top: 4px;
}
.upload-btn:hover { background: rgba(128,128,128,0.08); }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────
def get_groq() -> Groq:
    return Groq(api_key=os.environ["GROQ_API_KEY"])


def get_llm() -> GroqLLM:
    return GroqLLM(
        model=GROQ_MODEL,
        api_key=os.environ["GROQ_API_KEY"],
        temperature=0.2,
    )


def badge_html(module: str) -> str:
    labels = {
        "rag":              ("Documents",       "rag"),
        "bdd":              ("Base de donnees", "bdd"),
        "email_lire":       ("Email",           "email"),
        "email_repondre":   ("Email",           "email"),
        "email_envoyer":    ("Email",           "email"),
        "email_programmer": ("Email programme", "email"),
        "veille":           ("Veille web",      "veille"),
        "multi":            ("Multi-module",    "multi"),
        "general":          ("General",         "gen"),
        "rapport":          ("Rapport",         "rapport"),
    }
    label, cls = labels.get(module, ("General", "gen"))
    return f'<span class="badge badge-{cls}">{label}</span>'


def _charger_emails_disponibles(max_results: int = MAX_EMAILS) -> list:
    emails = []
    try:
        emails = gmail_lire(max_results=max_results)
    except Exception as e:
        st.warning(f"Gmail indisponible : {e}")

    if not emails:
        outlook_email = os.environ.get("OUTLOOK_EMAIL", "")
        outlook_pass  = os.environ.get("OUTLOOK_PASSWORD", "")
        if outlook_email and outlook_pass:
            try:
                emails = outlook_lire(max_results=max_results)
            except Exception as e:
                st.warning(f"Outlook indisponible : {e}")

    if emails:
        with st.spinner("Analyse des priorites..."):
            emails = analyser_priorites_batch(emails)

    return emails


# ──────────────────────────────────────────
# INDEXATION DOCUMENTS
# ──────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def charger_index_docs(fichiers_tuple: tuple) -> tuple:
    """
    Retourne (index, documents).
    Les documents bruts sont conserves pour le retriever BM25.
    """
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")
    documents = [d for f in fichiers_tuple if (d := load_doc(Path(f)))]
    if not documents:
        return None, None
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col    = chroma_client.get_or_create_collection("docs_active")
    vs     = ChromaVectorStore(chroma_collection=col)
    sc     = StorageContext.from_defaults(vector_store=vs)
    index  = VectorStoreIndex.from_documents(documents, storage_context=sc)
    return index, documents


# ──────────────────────────────────────────
# MOTEUR DE CHAT AVEC MEMOIRE
# Branche query.py dans Streamlit via session_state
# ──────────────────────────────────────────
def get_chat_engine(index: VectorStoreIndex, documents: list) -> CondensePlusContextChatEngine:
    """
    Retourne le moteur de chat avec memoire et retriever hybride (vectoriel + BM25 + reranking).
    Si l'index a change, reinitialise le moteur.
    """
    if (
        "chat_engine" not in st.session_state
        or st.session_state.get("chat_engine_index_id") != id(index)
    ):
        llm    = get_llm()
        memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

        # Retriever hybride : vectoriel + BM25 + reranking
        try:
            retriever = construire_retriever(index=index, documents=documents, reranking=True)
        except Exception as e:
            # Fallback sur le retriever vectoriel simple si une dependance manque
            import logging
            logging.getLogger(__name__).warning(
                "Retriever hybride indisponible (%s). Fallback vectoriel.", e
            )
            retriever = index.as_retriever(similarity_top_k=5)

        engine = CondensePlusContextChatEngine.from_defaults(
            retriever=retriever,
            llm=llm,
            memory=memory,
            system_prompt=SYSTEM_PROMPT_RAG,
            verbose=False,
        )
        st.session_state["chat_engine"]          = engine
        st.session_state["chat_engine_index_id"] = id(index)

    return st.session_state["chat_engine"]


# ──────────────────────────────────────────
# ROUTEUR
# ──────────────────────────────────────────
ROUTER_PROMPT = """Tu es un routeur d'agent IA d'entreprise. Analyse la question et reponds UNIQUEMENT en JSON valide.

Modules disponibles :
- "rag"              -> questions sur documents PDF/DOCX/TXT (contrats, guides, procedures)
- "rapport"          -> generer un resume, briefing, rapport ou analyse structuree d'un document
- "bdd"              -> base de donnees (employes, ventes, produits, factures, commandes, stocks)
- "email_lire"       -> lire, chercher, resumer des emails recus
- "email_repondre"   -> rediger une reponse professionnelle a un email
- "email_envoyer"    -> envoyer un nouvel email immediatement
- "email_programmer" -> programmer l'envoi d'un email a une heure precise ou dans X minutes/heures
- "veille"           -> recherche web en temps reel, actualites, tendances, informations recentes
- "multi"            -> necessite plusieurs modules combines
- "general"          -> salutation, conversation, question hors perimetre

Regle : si la demande contient "resume", "briefing", "rapport", "analyse", "synthese" -> utilise "rapport".
Regle : si la demande contient "programmer", "dans X minutes", "dans X heures", "a 14h" -> utilise "email_programmer".
Regle : si la demande concerne des actualites, tendances, informations recentes, recherche internet -> utilise "veille".

Reponds UNIQUEMENT avec ce JSON :
{{"module": "...", "raison": "courte explication", "modules_multi": []}}

Question : {question}"""


def router(groq_client: Groq, question: str) -> dict:
    resp = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": ROUTER_PROMPT.format(question=question)}],
        temperature=0.0,
    )
    text = resp.choices[0].message.content.strip().replace("```json", "").replace("```", "")
    try:
        return json.loads(text)
    except Exception:
        return {"module": "rag", "raison": "fallback"}


# ──────────────────────────────────────────
# EXECUTEURS
# ──────────────────────────────────────────
def run_rag(question: str) -> str:
    index     = st.session_state.get("index_docs")
    documents = st.session_state.get("docs_bruts", [])
    if not index:
        return "Aucun document charge. Chargez des documents dans la barre laterale."
    try:
        engine   = get_chat_engine(index, documents)
        response = engine.chat(question)
        sources  = list({
            node.metadata.get("file_name", "inconnu")
            for node in (response.source_nodes or [])
        })
        src_txt = ", ".join(f"`{s}`" for s in sources) if sources else "non disponible"
        return f"{response.response}\n\n*Sources : {src_txt}*"
    except Exception as e:
        return f"Erreur RAG : {e}"


def run_rapport(question: str) -> str:
    index = st.session_state.get("index_docs")
    if not index:
        return "Aucun document charge. Chargez un document dans la barre laterale."
    try:
        Settings.llm = get_llm()
        res      = index.as_query_engine(similarity_top_k=8).query(question)
        contexte = str(res.response)
        for node in res.source_nodes:
            contexte += "\n\n" + node.text[:1000]

        with st.spinner("Generation du rapport en cours..."):
            result = creer_rapport(
                contexte=contexte,
                question=question,
                output_dir=RAPPORTS_DIR,
            )

        rapport   = result["rapport"]
        path_pdf  = Path(result["path_pdf"])
        path_docx = Path(result["path_docx"])
        type_r    = result["type"]

        st.session_state["dernier_rapport"] = {
            "path_pdf":  str(path_pdf),
            "path_docx": str(path_docx),
            "titre":     rapport.get("titre", "Rapport"),
            "type":      type_r,
        }

        col1, col2 = st.columns(2)
        with col1:
            with open(path_pdf, "rb") as f:
                st.download_button(
                    "Telecharger PDF",
                    data=f.read(),
                    file_name=path_pdf.name,
                    mime="application/pdf",
                    use_container_width=True,
                )
        with col2:
            with open(path_docx, "rb") as f:
                st.download_button(
                    "Telecharger Word",
                    data=f.read(),
                    file_name=path_docx.name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )

        apercu = f"**{rapport.get('titre')}**\n\n"
        if type_r == "resume":
            apercu += "**Points cles :**\n"
            for p in rapport.get("points_cles", []):
                apercu += f"- {p}\n"
        else:
            apercu += f"**Resume executif :** {rapport.get('resume_executif', '')}\n\n"
            for s in rapport.get("sections", []):
                apercu += f"**{s['titre']}**\n{s['contenu']}\n\n"
            if rapport.get("recommandations"):
                apercu += "**Recommandations :**\n"
                for r in rapport["recommandations"]:
                    apercu += f"- {r}\n"
        if rapport.get("conclusion"):
            apercu += f"\n**Conclusion :** {rapport['conclusion']}"

        apercu += "\n\n*Rapport disponible dans la barre laterale pour envoi par email.*"
        return apercu

    except Exception as e:
        return f"Erreur generation rapport : {e}"


def run_bdd(question: str) -> tuple:
    """
    Retourne (reponse_str, figure_plotly_ou_None).
    """
    try:
        result = bdd_answer(question)
        return result["reponse"], result.get("figure")
    except Exception as e:
        return f"Erreur BDD : {e}", None


def run_veille(question: str) -> str:
    """Recherche web en temps reel via Tavily + synthese LLM."""
    try:
        resultat   = veille_recherche(question, nb_resultats=5, optimiser=True)
        reponse    = resultat["reponse"]
        sources    = resultat["sources"]
        requete    = resultat["requete"]
        nb_sources = resultat["nb_sources"]

        if nb_sources == 0:
            return "Aucun resultat trouve pour cette recherche. Reformulez votre question."

        sources_md = "\n".join([
            f"- [{s['titre']}]({s['url']})"
            for s in sources
        ])

        return (
            f"{reponse}\n\n"
            f"---\n"
            f"*Requete utilisee : `{requete}`*\n\n"
            f"*Sources ({nb_sources}) :*\n{sources_md}"
        )
    except ValueError as e:
        return f"Configuration manquante : {e}"
    except ImportError as e:
        return f"Dependance manquante : {e}"
    except Exception as e:
        return f"Erreur veille web : {e}"

def run_email_lire(question: str) -> str:
    try:
        emails = st.session_state.get("emails_charges", [])
        if not emails:
            emails = _charger_emails_disponibles()
            if emails:
                st.session_state["emails_charges"] = emails
        if not emails:
            return "Aucun email trouve. Actualisez la boite dans la barre laterale."
        index = st.session_state.get("index_emails") or indexer_emails(emails)
        st.session_state["index_emails"] = index
        if index:
            return repondre_sur_emails(index, question)
        return resumer_emails(emails)
    except Exception as e:
        return f"Erreur lecture emails : {e}"


def run_email_repondre(groq_client: Groq, question: str) -> str:
    try:
        emails = st.session_state.get("emails_charges", [])
        if not emails:
            emails = _charger_emails_disponibles()
            st.session_state["emails_charges"] = emails
        index = st.session_state.get("index_emails") or indexer_emails(emails)
        st.session_state["index_emails"] = index
        if not index:
            return "Impossible de charger le contexte email."
        resultat = generer_email_professionnel(index, question)
        sujet    = resultat.get("sujet", "Sans sujet")
        corps    = resultat.get("corps", "")
        st.session_state["brouillon_email"] = {
            "sujet": sujet, "corps": corps, "question": question
        }
        return (
            f"**Brouillon genere :**\n\n"
            f"**Sujet :** {sujet}\n\n"
            f"{corps}\n\n"
            f"*Rendez-vous dans la barre laterale pour envoyer ce brouillon.*"
        )
    except Exception as e:
        return f"Erreur redaction email : {e}"


def run_email_envoyer(groq_client: Groq, question: str) -> str:
    try:
        extraction = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content":
                f'Extrais les infos d\'envoi depuis ce texte. '
                f'JSON uniquement : {{"destinataire":"...","sujet":"...","instruction":"..."}} '
                f'Si l\'email est absent, mets "a_preciser". Texte : {question}'
            }],
            temperature=0.1,
        )
        infos = json.loads(
            extraction.choices[0].message.content.strip()
            .replace("```json", "").replace("```", "")
        )
        dest        = infos.get("destinataire", "a_preciser")
        sujet       = infos.get("sujet", "")
        instruction = infos.get("instruction", question)

        if dest == "a_preciser" or "@" not in str(dest):
            st.session_state["email_a_envoyer"] = {"sujet": sujet, "instruction": instruction}
            return "Destinataire non trouve. Precisez-le dans la barre laterale."

        corps, msg_id = gmail_generer_envoyer(dest, sujet, instruction)
        return f"**Email envoye a {dest}** (ID : `{msg_id}`)\n\n{corps}"
    except Exception as e:
        return f"Erreur envoi email : {e}"


def run_email_programmer(groq_client: Groq, question: str) -> str:
    try:
        extraction = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content":
                f'Extrais les informations pour programmer un email. '
                f'Reponds UNIQUEMENT en JSON : '
                f'{{"destinataire":"...","sujet":"...","instruction":"...","delai_minutes":null,"date_envoi":null}} '
                f'Regles : "dans X minutes/heures" -> delai_minutes. '
                f'Date precise -> date_envoi au format JJ/MM/YYYY HH:MM. '
                f'Destinataire absent -> "a_preciser". '
                f'Texte : {question}'
            }],
            temperature=0.1,
        )
        infos = json.loads(
            extraction.choices[0].message.content.strip()
            .replace("```json", "").replace("```", "")
        )
        dest        = infos.get("destinataire", "a_preciser")
        sujet       = infos.get("sujet", "")
        instruction = infos.get("instruction", question)
        delai       = infos.get("delai_minutes")
        date_str    = infos.get("date_envoi")

        if dest == "a_preciser" or "@" not in str(dest):
            st.session_state["email_programme_en_attente"] = infos
            return "Destinataire manquant. Completez dans la barre laterale."

        # Generer le corps de l'email
        g = Groq(api_key=os.environ["GROQ_API_KEY"])
        resp_corps = g.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Tu es un assistant professionnel. Redige un email clair et poli."},
                {"role": "user",   "content": f"Redige un email. Instruction : {instruction}. Destinataire : {dest}. Sujet : {sujet}"},
            ],
        )
        corps = resp_corps.choices[0].message.content

        # Calculer le moment d'envoi
        if delai:
            quand          = timedelta(minutes=int(delai))
            heure_affichee = (datetime.now() + quand).strftime("%d/%m/%Y a %H:%M")
        elif date_str:
            quand          = datetime.strptime(date_str, "%d/%m/%Y %H:%M")
            heure_affichee = quand.strftime("%d/%m/%Y a %H:%M")
        else:
            quand          = timedelta(hours=1)
            heure_affichee = (datetime.now() + quand).strftime("%d/%m/%Y a %H:%M")

        programmer_email(
            destinataire=dest,
            sujet=sujet,
            corps=corps,
            quand=quand,
        )
        return (
            f"**Email programme avec succes.**\n\n"
            f"- Destinataire : {dest}\n"
            f"- Sujet : {sujet}\n"
            f"- Envoi prevu : {heure_affichee}\n\n"
            f"*Vous pouvez voir et annuler les emails programmes dans la barre laterale.*"
        )
    except Exception as e:
        return f"Erreur programmation email : {e}"


# ──────────────────────────────────────────
# ORCHESTRATEUR
# ──────────────────────────────────────────
def orchestrer(question: str) -> tuple[str, str]:
    groq_client = get_groq()

    # Commande : liste des fichiers disponibles
    mots_liste = ["liste", "quels fichiers", "quels documents", "montre les fichiers", "affiche les documents"]
    if any(m in question.lower() for m in mots_liste):
        fichiers = st.session_state.get("fichiers_scannes", [])
        if not fichiers:
            return "Aucun dossier scanne. Utilisez le bouton Scanner dans la barre laterale.", "general"
        liste   = "\n".join([f"- `{f.name}` ({f.suffix.upper()[1:]})" for f in fichiers])
        dossier = st.session_state.get("dossier_actif", "inconnu")
        return f"Dossier : `{dossier}`\n\n**{len(fichiers)} fichier(s) disponible(s) :**\n{liste}", "general"

    decision = router(groq_client, question)
    module   = decision.get("module", "general")

    if module == "rag":
        return run_rag(question), "rag"
    elif module == "rapport":
        return run_rapport(question), "rapport"
    elif module == "bdd":
        reponse_bdd, figure_bdd = run_bdd(question)
        # Stocker la figure en session pour l'afficher dans main()
        if figure_bdd is not None:
            st.session_state["derniere_figure_bdd"] = figure_bdd
        else:
            st.session_state.pop("derniere_figure_bdd", None)
        return reponse_bdd, "bdd"
    elif module == "email_lire":
        return run_email_lire(question), "email_lire"
    elif module == "email_repondre":
        return run_email_repondre(groq_client, question), "email_repondre"
    elif module == "email_envoyer":
        return run_email_envoyer(groq_client, question), "email_envoyer"
    elif module == "email_programmer":
        return run_email_programmer(groq_client, question), "email_programmer"
    elif module == "veille":
        return run_veille(question), "veille"
    elif module == "multi":
        modules_list = decision.get("modules_multi", ["rag"])
        resultats    = []
        for mod in modules_list:
            if mod == "rag":
                resultats.append(f"**[Documents]**\n{run_rag(question)}")
            elif mod == "rapport":
                resultats.append(f"**[Rapport]**\n{run_rapport(question)}")
            elif mod == "bdd":
                resultats.append(f"**[BDD]**\n{run_bdd(question)}")
            elif mod == "email_lire":
                resultats.append(f"**[Emails]**\n{run_email_lire(question)}")
        synthese = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content":
                f"Synthetise pour repondre a : '{question}'\n\n" + "\n\n---\n\n".join(resultats)
            }],
            temperature=0.2,
        )
        return synthese.choices[0].message.content, "multi"
    else:
        resp = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": "Tu es un assistant d'entreprise intelligent."},
                {"role": "user",   "content": question},
            ],
            temperature=0.5,
        )
        return resp.choices[0].message.content, "general"


# ──────────────────────────────────────────
# INTERFACE PRINCIPALE
# ──────────────────────────────────────────
def main():

    # ── SIDEBAR ──
    with st.sidebar:
        st.markdown(
            "<div style='padding:16px 0 8px'>"
            "<span style='font-size:15px;font-weight:600'>Agent IA</span><br>"
            "<span style='font-size:11px;opacity:.5'>Entreprise</span></div>",
            unsafe_allow_html=True,
        )
        st.divider()

        doc_ok    = bool(st.session_state.get("index_docs"))
        email_ok  = bool(st.session_state.get("emails_charges"))
        tavily_ok = bool(os.environ.get("TAVILY_API_KEY", ""))

        for label, actif in [
            ("Documents",       doc_ok),
            ("Base de donnees", True),
            ("Emails",          email_ok),
            ("Veille web",      tavily_ok),
        ]:
            dot = "dot-on" if actif else "dot-off"
            st.markdown(
                f'<div class="module-row"><span class="dot {dot}"></span><span>{label}</span></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── Documents ──
        with st.expander("Documents", expanded=not doc_ok):
            st.caption("Selectionnez un ou plusieurs fichiers")
            fichiers_upload = st.file_uploader(
                "Fichiers",
                type=["pdf","docx","txt","xlsx","csv","pptx","md"],
                accept_multiple_files=True,
                label_visibility="collapsed",
            )
            if fichiers_upload:
                st.caption(f"{len(fichiers_upload)} fichier(s) selectionne(s)")
                if st.button("Charger et indexer", type="primary", use_container_width=True):
                    import tempfile, shutil
                    tmp_dir = Path(tempfile.mkdtemp())
                    try:
                        chemins_tmp = []
                        for f in fichiers_upload:
                            p = tmp_dir / f.name
                            p.write_bytes(f.read())
                            chemins_tmp.append(str(p))
                        with st.spinner("Indexation..."):
                            idx, docs = charger_index_docs(tuple(chemins_tmp))
                            st.session_state["index_docs"]        = idx
                            st.session_state["docs_bruts"]        = docs or []
                            st.session_state["docs_charges_noms"] = [f.name for f in fichiers_upload]
                            st.session_state.pop("chat_engine", None)
                            st.session_state.pop("chat_engine_index_id", None)
                        if idx:
                            st.success(f"{len(chemins_tmp)} fichier(s) charge(s)")
                        else:
                            st.error("Aucun document lisible.")
                    finally:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
            elif "docs_charges_noms" in st.session_state:
                st.caption(", ".join(st.session_state["docs_charges_noms"]))

        # ── Emails ──
        with st.expander("Emails", expanded=False):
            nb = st.slider("Nb emails", 5, 50, MAX_EMAILS, label_visibility="collapsed")
            if st.button("Actualiser", use_container_width=True):
                with st.spinner("Recuperation..."):
                    emails = _charger_emails_disponibles(nb)
                    if emails:
                        st.session_state["emails_charges"] = emails
                        st.session_state["index_emails"]   = indexer_emails(emails)
                        st.success(f"{len(emails)} email(s)")
                    else:
                        st.error("Verifiez Gmail (token.json).")
            if st.session_state.get("emails_charges"):
                st.caption(f"{len(st.session_state['emails_charges'])} emails charges")

        # ── Rapport ──
        if "dernier_rapport" in st.session_state:
            st.divider()
            r = st.session_state["dernier_rapport"]
            with st.expander("Envoyer le rapport", expanded=True):
                st.caption(r["titre"])
                dest_r   = st.text_input("Destinataire", key="dest_rapport")
                format_r = st.radio("Format", ["PDF","Word","Les deux"], horizontal=True, key="fmt_rapport")
                if st.button("Envoyer", type="primary", use_container_width=True):
                    with st.spinner("Envoi..."):
                        try:
                            import base64
                            from email.mime.multipart import MIMEMultipart
                            from email.mime.base import MIMEBase
                            from email.mime.text import MIMEText
                            from email import encoders
                            from module_email.gmail_reader import get_service
                            service = get_service()
                            msg = MIMEMultipart()
                            msg["To"] = dest_r
                            msg["Subject"] = f"[Rapport IA] {r['titre']}"
                            msg.attach(MIMEText(f"Rapport : {r['titre']}", "plain"))
                            atts = []
                            if format_r in ["PDF","Les deux"]:
                                atts.append((r["path_pdf"], "application/pdf"))
                            if format_r in ["Word","Les deux"]:
                                atts.append((r["path_docx"],
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
                            for pa, mt in atts:
                                with open(pa,"rb") as f:
                                    part = MIMEBase(*mt.split("/"))
                                    part.set_payload(f.read())
                                    encoders.encode_base64(part)
                                    part.add_header("Content-Disposition", f"attachment; filename={Path(pa).name}")
                                    msg.attach(part)
                            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                            service.users().messages().send(userId="me", body={"raw": raw}).execute()
                            st.success(f"Envoye a {dest_r}")
                            del st.session_state["dernier_rapport"]
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")

        # ── Brouillon ──
        if "brouillon_email" in st.session_state:
            st.divider()
            b = st.session_state["brouillon_email"]
            with st.expander("Brouillon", expanded=True):
                dest  = st.text_input("Destinataire", key="dest_brouillon")
                sujet = st.text_input("Sujet", value=b["sujet"], key="sujet_brouillon")
                corps = st.text_area("Message", value=b["corps"], height=120, key="corps_brouillon")
                if st.button("Envoyer", type="primary", use_container_width=True):
                    gmail_envoyer(dest, sujet, corps)
                    st.success(f"Envoye a {dest}")
                    del st.session_state["brouillon_email"]
                    st.rerun()

        # ── Emails programmes ──
        jobs = lister_emails_programmes()
        if jobs:
            st.divider()
            with st.expander(f"Programmes ({len(jobs)})", expanded=False):
                for job in jobs:
                    st.caption(job["nom"])
                    st.caption(f"Envoi : {job['run_date']}")
                    if st.button("Annuler", key=f"cancel_{job['id']}", use_container_width=True):
                        if annuler_email_programme(job["id"]):
                            st.success("Annule")
                            st.rerun()
                    st.divider()

        if "email_a_envoyer" in st.session_state:
            st.divider()
            e = st.session_state["email_a_envoyer"]
            with st.expander("Completer l'envoi", expanded=True):
                dest = st.text_input("Destinataire", key="dest_manquant")
                if st.button("Generer et envoyer", use_container_width=True):
                    corps, mid = gmail_generer_envoyer(dest, e["sujet"], e["instruction"])
                    st.success(f"Envoye. ID : {mid}")
                    del st.session_state["email_a_envoyer"]
                    st.rerun()

        st.divider()
        if st.button("Nouvelle conversation", use_container_width=True):
            st.session_state["messages"] = []
            st.session_state.pop("conv_id_actif", None)
            st.session_state.pop("chat_engine", None)
            st.session_state.pop("chat_engine_index_id", None)
            st.session_state.pop("derniere_figure_bdd", None)
            st.rerun()

    # ── ZONE PRINCIPALE — deux onglets ──
    onglet_chat, onglet_historique = st.tabs(["  Chat  ", "  Historique  "])

    # ════════════════════════════════════════
    # ONGLET CHAT
    # ════════════════════════════════════════
    with onglet_chat:
        st.markdown(
            "<div class='main-title'>Agent IA Entreprise</div>"
            "<div class='main-sub'>Posez votre question — le bon module est choisi automatiquement.</div>",
            unsafe_allow_html=True,
        )

        # Topbar statut
        doc_ok    = bool(st.session_state.get("index_docs"))
        email_ok  = bool(st.session_state.get("emails_charges"))
        tavily_ok = bool(os.environ.get("TAVILY_API_KEY", ""))
        items = [("Documents", doc_ok), ("Base de donnees", True),
                 ("Emails", email_ok), ("Veille web", tavily_ok)]
        badges = " ".join([
            f'<span class="tb-badge {"tb-on" if a else "tb-off"}">{l}</span>'
            for l, a in items
        ])
        st.markdown(f'<div class="topbar">{badges}</div>', unsafe_allow_html=True)

        # Init conversation
        if "messages" not in st.session_state:
            st.session_state["messages"] = []
            st.session_state["messages"].append({
                "role": "assistant",
                "content": (
                    "Bonjour. Je suis votre agent IA d'entreprise.\n\n"
                    "Je peux repondre sur :\n"
                    "- Vos documents (PDF, DOCX, XLSX, PPTX, CSV)\n"
                    "- Rapports et briefings\n"
                    "- Votre base de donnees (ventes, employes, produits)\n"
                    "- Vos emails\n"
                    "- Actualites et veille web en temps reel\n\n"
                    "Commencez par charger des fichiers dans la barre laterale."
                ),
                "module": "general",
            })

        # Afficher messages
        for msg in st.session_state["messages"]:
            with st.chat_message(msg["role"]):
                if msg["role"] == "assistant" and msg.get("module"):
                    st.markdown(badge_html(msg["module"]), unsafe_allow_html=True)
                st.markdown(msg["content"])
                # Afficher graphique BDD si present dans le message
                if msg.get("figure"):
                    st.plotly_chart(msg["figure"], use_container_width=True)

        # Input utilisateur
        if question := st.chat_input("Posez votre question..."):
            # Init conversation en BDD si premiere question
            if "conv_id_actif" not in st.session_state:
                titre = generer_titre(question)
                conv_id = nouvelle_conversation(titre)
                st.session_state["conv_id_actif"] = conv_id

            conv_id = st.session_state["conv_id_actif"]

            # Sauvegarder question
            sauvegarder_message(conv_id, "user", question, "general")
            st.session_state["messages"].append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.markdown(question)

            # Generer reponse
            with st.chat_message("assistant"):
                with st.spinner("Traitement en cours..."):
                    reponse, module = orchestrer(question)

                st.markdown(badge_html(module), unsafe_allow_html=True)
                st.markdown(reponse)

                # Afficher graphique si BDD
                figure = st.session_state.pop("derniere_figure_bdd", None)
                if figure is not None:
                    st.plotly_chart(figure, use_container_width=True)

            # Sauvegarder reponse
            sauvegarder_message(conv_id, "assistant", reponse, module)

            # Maj titre apres 2eme message
            if compter_messages(conv_id) == 4:
                mettre_a_jour_titre(conv_id, generer_titre(question))

            msg_data = {"role": "assistant", "content": reponse, "module": module}
            if figure is not None:
                msg_data["figure"] = figure
            st.session_state["messages"].append(msg_data)

    # ════════════════════════════════════════
    # ONGLET HISTORIQUE
    # ════════════════════════════════════════
    with onglet_historique:
        st.markdown(
            "<div class='main-title'>Historique</div>"
            "<div class='main-sub'>Retrouvez toutes vos conversations precedentes.</div>",
            unsafe_allow_html=True,
        )

        conversations = lister_conversations(limite=50)

        if not conversations:
            st.info("Aucune conversation enregistree pour l'instant.")
        else:
            st.caption(f"{len(conversations)} conversation(s) enregistree(s)")
            st.divider()

            for conv in conversations:
                date_brute = conv["date_maj"][:16].replace("T", " ")
                nb_msgs    = compter_messages(conv["id"])

                col_titre, col_date, col_action = st.columns([5, 2, 1])

                with col_titre:
                    if st.button(
                        f"{conv['titre']}",
                        key=f"conv_{conv['id']}",
                        use_container_width=True,
                    ):
                        st.session_state["conv_detail"] = conv["id"]

                with col_date:
                    st.caption(date_brute)
                    st.caption(f"{nb_msgs} messages")

                with col_action:
                    if st.button("X", key=f"del_{conv['id']}"):
                        supprimer_conversation(conv["id"])
                        if st.session_state.get("conv_detail") == conv["id"]:
                            st.session_state.pop("conv_detail", None)
                        st.rerun()

            # Detail d'une conversation selectionnee
            if "conv_detail" in st.session_state:
                st.divider()
                conv_id_detail = st.session_state["conv_detail"]
                messages_detail = charger_messages(conv_id_detail)

                # Trouver le titre
                titre_detail = next(
                    (c["titre"] for c in conversations if c["id"] == conv_id_detail),
                    "Conversation"
                )
                st.subheader(titre_detail)

                for msg in messages_detail:
                    with st.chat_message(msg["role"]):
                        if msg["role"] == "assistant" and msg.get("module"):
                            st.markdown(badge_html(msg["module"]), unsafe_allow_html=True)
                        st.markdown(msg["contenu"])
                        ts = msg.get("timestamp", "")[:16].replace("T", " ")
                        st.caption(ts)

                if st.button("Reprendre cette conversation", type="primary"):
                    # Charger les messages dans le chat actif
                    st.session_state["messages"] = []
                    for msg in messages_detail:
                        st.session_state["messages"].append({
                            "role":    msg["role"],
                            "content": msg["contenu"],
                            "module":  msg.get("module", "general"),
                        })
                    st.session_state["conv_id_actif"] = conv_id_detail
                    st.session_state.pop("conv_detail", None)
                    st.rerun()



if __name__ == "__main__":
    main()

