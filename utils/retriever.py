"""
utils/retriever.py
Retriever hybride : recherche vectorielle + BM25 + reranking cross-encoder.

Pipeline :
  1. Recherche vectorielle  -> top_k candidats
  2. Recherche BM25         -> top_k candidats
  3. Fusion RRF (Reciprocal Rank Fusion) des deux listes
  4. Reranking cross-encoder sur les candidats fusionnes
  5. Retourne les N meilleurs chunks au LLM
"""

import logging
from llama_index.core import VectorStoreIndex
from llama_index.core.schema import NodeWithScore, QueryBundle
from llama_index.core.retrievers import BaseRetriever, VectorIndexRetriever
from llama_index.retrievers.bm25 import BM25Retriever

logger = logging.getLogger(__name__)

# Nombre de candidats recuperes par chaque retriever avant fusion
CANDIDATS_PAR_RETRIEVER = 10

# Nombre de chunks gardes apres reranking pour le LLM
TOP_K_FINAL = 5


def fusion_rrf(
    resultats_vectoriel: list[NodeWithScore],
    resultats_bm25: list[NodeWithScore],
    k: int = 60,
) -> list[NodeWithScore]:
    """
    Reciprocal Rank Fusion : combine deux listes de resultats classees.
    Formule : score_rrf = sum(1 / (k + rang)) pour chaque liste.
    k=60 est la valeur standard de la litterature.
    """
    scores: dict[str, float]         = {}
    nodes:  dict[str, NodeWithScore] = {}

    for rang, node in enumerate(resultats_vectoriel, start=1):
        nid = node.node.node_id
        scores[nid] = scores.get(nid, 0.0) + 1.0 / (k + rang)
        nodes[nid]  = node

    for rang, node in enumerate(resultats_bm25, start=1):
        nid = node.node.node_id
        scores[nid] = scores.get(nid, 0.0) + 1.0 / (k + rang)
        nodes[nid]  = node

    tries = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        NodeWithScore(node=nodes[nid].node, score=score)
        for nid, score in tries
    ]


def reranker_chunks(
    question: str,
    chunks: list[NodeWithScore],
    top_n: int = TOP_K_FINAL,
) -> list[NodeWithScore]:
    """
    Reranking avec un cross-encoder sentence-transformers.
    Le modele relit chaque (question, chunk) ensemble et produit un score de pertinence reel.
    Modele utilise : cross-encoder/ms-marco-MiniLM-L-6-v2 (leger, rapide, multilingue partiel)
    """
    try:
        from sentence_transformers import CrossEncoder
        model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

        paires = [(question, node.node.get_content()) for node in chunks]
        scores = model.predict(paires)

        chunks_scores = list(zip(chunks, scores))
        chunks_scores.sort(key=lambda x: x[1], reverse=True)

        return [
            NodeWithScore(node=node.node, score=float(score))
            for node, score in chunks_scores[:top_n]
        ]

    except ImportError:
        logger.warning(
            "sentence-transformers non installe. "
            "Reranking desactive — pip install sentence-transformers"
        )
        return chunks[:top_n]
    except Exception as e:
        logger.warning("Reranking echoue (%s). Retour sans reranking.", e)
        return chunks[:top_n]


class HybridRetriever(BaseRetriever):
    """
    Retriever hybride combinant recherche vectorielle, BM25 et reranking.
    Utilisation :
        retriever = HybridRetriever(index, documents)
        nodes = retriever.retrieve("ma question")
    """

    def __init__(
        self,
        index: VectorStoreIndex,
        documents: list,
        top_k_candidats: int = CANDIDATS_PAR_RETRIEVER,
        top_k_final: int = TOP_K_FINAL,
        reranking: bool = True,
    ):
        self._vector_retriever = VectorIndexRetriever(
            index=index,
            similarity_top_k=top_k_candidats,
        )
        self._bm25_retriever = BM25Retriever.from_defaults(
            nodes=documents,
            similarity_top_k=top_k_candidats,
        )
        self._top_k_final = top_k_final
        self._reranking   = reranking
        super().__init__()

    def _retrieve(self, query_bundle: QueryBundle) -> list[NodeWithScore]:
        question = query_bundle.query_str

        # 1. Recherche vectorielle
        try:
            res_vectoriel = self._vector_retriever.retrieve(query_bundle)
        except Exception as e:
            logger.warning("Recherche vectorielle echouee : %s", e)
            res_vectoriel = []

        # 2. Recherche BM25
        try:
            res_bm25 = self._bm25_retriever.retrieve(query_bundle)
        except Exception as e:
            logger.warning("Recherche BM25 echouee : %s", e)
            res_bm25 = []

        if not res_vectoriel and not res_bm25:
            return []

        # 3. Fusion RRF
        candidats = fusion_rrf(res_vectoriel, res_bm25)

        # 4. Reranking
        if self._reranking and candidats:
            return reranker_chunks(question, candidats, top_n=self._top_k_final)

        return candidats[:self._top_k_final]


def construire_retriever(
    index: VectorStoreIndex,
    documents: list,
    reranking: bool = True,
) -> HybridRetriever:
    """
    Fonction utilitaire pour construire le retriever hybride.
    Appeler apres l'indexation des documents.

    Parametres :
        index     : VectorStoreIndex construit par charger_index_docs()
        documents : liste des Document LlamaIndex indexes (pour BM25)
        reranking : activer/desactiver le reranking cross-encoder
    """
    return HybridRetriever(
        index=index,
        documents=documents,
        reranking=reranking,
    )

