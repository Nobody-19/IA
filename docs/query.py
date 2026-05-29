import os
import chromadb
from pathlib import Path
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.core.chat_engine import CondensePlusContextChatEngine
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.llms.groq import Groq as GroqLLM
from ingest import main as selectionner_et_indexer

# ──────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_FILE)
Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")

TOP_K         = 5       # plus de chunks pour meilleure couverture
MAX_TOKENS    = 2048    # réponses plus complètes
TEMPERATURE   = 0.2     # rester factuel

# ──────────────────────────────────────────
# PROMPT SYSTEM AMÉLIORÉ
# ──────────────────────────────────────────
SYSTEM_PROMPT = """Tu es un assistant expert en analyse de documents.

Règles strictes :
1. Réponds UNIQUEMENT à partir des documents fournis dans le contexte.
2. Cite toujours le nom du fichier source entre [crochets] après chaque information clé.
3. Si plusieurs documents sont pertinents, synthétise les informations.
4. Si la réponse est absente des documents, dis : "Je ne trouve pas cette information dans les documents fournis."
5. Structure ta réponse avec des points clairs si la réponse est longue.
6. Réponds dans la même langue que la question."""

# ──────────────────────────────────────────
# INITIALISATION LLM
# ──────────────────────────────────────────
def get_llm():
    return GroqLLM(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        system_prompt=SYSTEM_PROMPT,
    )


# ──────────────────────────────────────────
# MOTEUR DE CHAT AVEC MÉMOIRE
# ──────────────────────────────────────────
def build_chat_engine(index, llm):
    """
    CondensePlusContextChatEngine :
    - Condense l'historique + la question en une requête de recherche
    - Récupère le contexte dans ChromaDB
    - Génère la réponse avec mémoire des échanges précédents
    """
    memory = ChatMemoryBuffer.from_defaults(token_limit=4096)

    retriever = index.as_retriever(
        similarity_top_k=TOP_K,
    )

    chat_engine = CondensePlusContextChatEngine.from_defaults(
        retriever=retriever,
        llm=llm,
        memory=memory,
        system_prompt=SYSTEM_PROMPT,
        verbose=False,
    )
    return chat_engine, memory


# ──────────────────────────────────────────
# AFFICHAGE DES SOURCES
# ──────────────────────────────────────────
def afficher_sources(response):
    """Affiche les sources avec score de pertinence et filtre les doublons."""
    if not response.source_nodes:
        print("  (aucune source trouvée)")
        return

    vues = set()
    sources_filtrees = []
    for node in response.source_nodes:
        fname = node.metadata.get("file_name", "inconnu")
        score = round(node.score or 0, 3)
        cle   = (fname, score)
        if cle not in vues:
            vues.add(cle)
            sources_filtrees.append((fname, score))

    # Trier par score décroissant
    sources_filtrees.sort(key=lambda x: x[1], reverse=True)

    print("\n📎 Sources utilisées :")
    for fname, score in sources_filtrees:
        barre = "█" * int(score * 10) + "░" * (10 - int(score * 10))
        print(f"   • {fname} [{barre}] {score}")


# ──────────────────────────────────────────
# COMMANDE : LISTER LES SOURCES INDEXÉES
# ──────────────────────────────────────────
def lister_sources_indexees(index):
    """Affiche tous les fichiers présents dans l'index."""
    try:
        docs = index.docstore.docs
        fichiers = sorted(set(
            doc.metadata.get("file_name", "inconnu")
            for doc in docs.values()
        ))
        print(f"\n📚 {len(fichiers)} fichier(s) indexé(s) :")
        for f in fichiers:
            print(f"   - {f}")
    except Exception:
        print("⚠️  Impossible de lister les sources (accès docstore indisponible).")


# ──────────────────────────────────────────
# BOUCLE PRINCIPALE
# ──────────────────────────────────────────
def main():
    index = selectionner_et_indexer()
    llm   = get_llm()
    chat_engine, memory = build_chat_engine(index, llm)

    print("\n" + "="*55)
    print("  🤖 Agent pret ! Pose tes questions.")
    print("  'changer'  → choisir d'autres fichiers")
    print("  'reset'    → vider la memoire de conversation")
    print("  'sources'  → lister les fichiers indexes")
    print("  'quitter'  → arreter")
    print("="*55 + "\n")

    while True:
        try:
            question = input("❓ Ta question : ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Au revoir !")
            break

        if not question:
            continue

        # ── Commandes spéciales ──
        if question.lower() == "quitter":
            print("👋 Au revoir !")
            break

        if question.lower() == "reset":
            memory.reset()
            print("🔄 Mémoire vidée. Nouvelle conversation.\n")
            continue

        if question.lower() == "sources":
            lister_sources_indexees(index)
            print()
            continue

        if question.lower() == "changer":
            index = selectionner_et_indexer()
            llm   = get_llm()
            chat_engine, memory = build_chat_engine(index, llm)
            print("\n✅ Nouveaux fichiers chargés ! Mémoire réinitialisée.\n")
            continue

        # ── Question normale ──
        print("\n🔍 Recherche en cours...")
        try:
            response = chat_engine.chat(question)
            print(f"\n💬 Réponse :\n{response.response}")
            afficher_sources(response)

        except Exception as e:
            print(f"❌ Erreur lors de la requête : {e}")

        print("-" * 55 + "\n")


if __name__ == "__main__":
    main()