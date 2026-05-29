"""
docs/ingest.py
Indexation des documents dans ChromaDB.
Utilise utils/loader.py pour le chargement — plus de duplication.
"""

import sys
import logging
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from llama_index.core import VectorStoreIndex, Settings, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

# Ajouter la racine au path pour les imports
BASE_DIR   = Path(__file__).parent.parent
DOCS_DIR   = BASE_DIR / "docs"
CHROMA_DIR = BASE_DIR / "chroma_db"
ENV_FILE   = BASE_DIR / ".env"

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from utils.loader import load_doc, EXTENSIONS_SUPPORTEES
from dotenv import load_dotenv

load_dotenv(dotenv_path=ENV_FILE)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

Settings.embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-m3")


def scanner_fichiers(dossier: Path = DOCS_DIR) -> list[Path]:
    return sorted([
        f for f in dossier.iterdir()
        if f.is_file()
        and f.suffix.lower() in EXTENSIONS_SUPPORTEES
        and not f.name.startswith(".")
    ])


def afficher_menu(fichiers: list[Path]) -> None:
    print("\n" + "=" * 55)
    print("      AGENT IA - Selection des documents")
    print("=" * 55)
    if not fichiers:
        print("  Aucun fichier trouve dans docs/")
        print("=" * 55)
        return
    print(f"  Dossier : {DOCS_DIR}")
    print(f"  {len(fichiers)} fichier(s) disponible(s) :\n")
    for i, f in enumerate(fichiers, 1):
        size_kb = f.stat().st_size // 1024
        ext_label = f.suffix.upper()[1:] if f.suffix else "?"
        print(f"  [{i:2}] [{ext_label:<5}]  {f.name:<38} ({size_kb} Ko)")
    print("\n  [ 0]  Tous les fichiers")
    print("=" * 55)


def selectionner_fichiers(fichiers: list[Path]) -> list[Path]:
    while True:
        choix = input("\n  Entrez les numeros (ex: 1,3) ou 0 pour tout : ").strip()
        if choix == "0":
            print(f"  Tous les fichiers selectionnes ({len(fichiers)})")
            return fichiers
        try:
            indices   = [int(x.strip()) for x in choix.split(",")]
            selection = []
            valide    = True
            for idx in indices:
                if 1 <= idx <= len(fichiers):
                    selection.append(fichiers[idx - 1])
                else:
                    print(f"  Numero invalide : {idx}")
                    valide = False
                    break
            if valide and selection:
                print("\n  Fichiers selectionnes :")
                for f in selection:
                    print(f"  > {f.name}")
                return selection
        except ValueError:
            print("  Format invalide. Exemple : 1,2,3 ou 0 pour tout")


def indexer_fichiers(
    fichiers: list[Path],
    collection_name: str = "session_active",
) -> VectorStoreIndex:
    print("\n  Chargement des documents...")
    documents = []
    for f in fichiers:
        doc = load_doc(f)
        if doc:
            documents.append(doc)
            print(f"  OK      : {f.name}")
        else:
            print(f"  Ignore  : {f.name}")

    if not documents:
        print("\n  Aucun document valide.")
        raise SystemExit(1)

    print(f"\n  Indexation de {len(documents)} document(s)...")

    # Eviter que le LLM soit appele pendant l'indexation
    llm_backup = Settings._llm
    Settings._llm = None

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    chroma = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        chroma.delete_collection(collection_name)
    except Exception:
        pass

    col   = chroma.get_or_create_collection(collection_name)
    vs    = ChromaVectorStore(chroma_collection=col)
    sc    = StorageContext.from_defaults(vector_store=vs)
    index = VectorStoreIndex.from_documents(documents, storage_context=sc, show_progress=True)

    if llm_backup is not None:
        Settings._llm = llm_backup

    print("  Indexation terminee.")
    return index


def main() -> VectorStoreIndex:
    fichiers  = scanner_fichiers()
    afficher_menu(fichiers)
    if not fichiers:
        raise SystemExit(1)
    selection = selectionner_fichiers(fichiers)
    return indexer_fichiers(selection)


if __name__ == "__main__":
    main()
