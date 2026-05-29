"""
module_email/email_agent.py
Indexation RAG des emails + generation de reponses et d'emails professionnels.
"""

import os
import json
import logging
from pathlib import Path

from dotenv import load_dotenv
from groq import Groq
from llama_index.core import VectorStoreIndex, Settings, StorageContext, Document
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import chromadb

BASE_DIR   = Path(__file__).parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"
ENV_FILE   = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

GROQ_MODEL = "llama-3.3-70b-versatile"
client = Groq(api_key=os.environ["GROQ_API_KEY"])


def emails_vers_documents(emails: list) -> list[Document]:
    docs = []
    for e in emails:
        texte = (
            f"De : {e['de']}\n"
            f"Date : {e['date']}\n"
            f"Sujet : {e['sujet']}\n\n"
            f"{e['corps']}"
        )
        docs.append(Document(
            text=texte,
            metadata={
                "file_name": f"email_{e['id'][:8]}",
                "sujet":     e["sujet"],
                "de":        e["de"],
                "date":      e["date"],
                "source":    e.get("source", "email"),
            }
        ))
    return docs


def indexer_emails(emails: list, collection_name: str = "emails_index") -> VectorStoreIndex | None:
    Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")
    Settings._llm = None

    documents = emails_vers_documents(emails)
    if not documents:
        return None

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))

    try:
        chroma.delete_collection(collection_name)
    except Exception:
        pass

    col   = chroma.get_or_create_collection(collection_name)
    vs    = ChromaVectorStore(chroma_collection=col)
    sc    = StorageContext.from_defaults(vector_store=vs)
    index = VectorStoreIndex.from_documents(documents, storage_context=sc)
    return index


def generer_email_professionnel(index: VectorStoreIndex, consigne: str) -> dict:
    """
    Genere un email professionnel au format JSON {sujet, corps}.
    Utilise le contexte des emails indexes pour personnaliser la reponse.
    """
    from llama_index.llms.groq import Groq as GroqLLM

    Settings.llm = GroqLLM(
        model=GROQ_MODEL,
        api_key=os.environ["GROQ_API_KEY"],
    )

    query_engine = index.as_query_engine(similarity_top_k=3)
    contexte     = query_engine.query(consigne)

    prompt = (
        f"Tu es un expert en communication professionnelle.\n"
        f"Contexte extrait des emails existants : {contexte}\n\n"
        f"Redige l'email demande : {consigne}\n\n"
        f"CONTRAINTES STRICTES :\n"
        f"- Reponds UNIQUEMENT en JSON valide.\n"
        f"- Commence le corps par 'Bonjour [Nom],'\n"
        f"- Termine par une signature professionnelle.\n"
        f"- Sauts de ligne avec \\n dans le corps.\n\n"
        f"FORMAT ATTENDU :\n"
        f'{{"sujet": "Objet du mail", "corps": "Contenu..."}}'
    )

    response = Settings.llm.complete(prompt)
    text     = response.text.strip().replace("```json", "").replace("```", "")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback : le LLM n'a pas respecte le format JSON
        return {
            "sujet": "Reponse concernant votre demande",
            "corps": response.text,
        }


def resumer_emails(emails: list) -> str:
    if not emails:
        return "Aucun email a resumer."

    texte = "\n\n".join([
        f"Email {i + 1} : {e['corps'][:500]}"
        for i, e in enumerate(emails[:10])
    ])

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": "Tu es un assistant qui resume les emails en francais de facon concise."},
            {"role": "user",   "content": f"Resume ces emails :\n\n{texte}"},
        ],
    )
    return response.choices[0].message.content


def rechercher_emails(emails: list, query: str) -> list:
    q = query.lower()
    return [
        e for e in emails
        if q in e["corps"].lower() or q in e["sujet"].lower()
    ]


def repondre_sur_emails(index: VectorStoreIndex, question: str) -> str:
    from llama_index.llms.groq import Groq as GroqLLM

    Settings.llm = GroqLLM(
        model=GROQ_MODEL,
        api_key=os.environ["GROQ_API_KEY"],
    )
    qe = index.as_query_engine(similarity_top_k=3)
    return str(qe.query(question))
