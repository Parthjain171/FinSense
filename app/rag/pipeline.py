"""
Core RAG pipeline.

Handles document ingestion, FAISS indexing, retrieval, and
cross-encoder reranking. Designed for financial documents
where retrieving the wrong client's invoice is not just
inaccurate but a compliance risk.

FAISS runs locally with zero external API calls. Financial
data for 300+ startup clients cannot leave a controlled
environment. This is a deliberate architectural choice.
"""

import os
import json
import glob
import faiss
import numpy as np
from typing import List, Optional

from app.parsers.pdf_parser import extract_invoice_text, extract_csv_financials
from app.rag.chunker import chunk_invoice, chunk_financial_statement


def _load_sentence_transformers(embedding_model, reranker_model):
    """Try to load sentence-transformers models. Returns None if unavailable.
    Set USE_TFIDF=true in env to skip loading entirely (e.g. Render free tier).
    """
    if os.getenv("USE_TFIDF", "").lower() in ("1", "true", "yes"):
        print("  USE_TFIDF=true: skipping sentence-transformers, using TF-IDF fallback.")
        return None, None
    try:
        from sentence_transformers import SentenceTransformer, CrossEncoder
        embedder = SentenceTransformer(embedding_model)
        reranker = CrossEncoder(reranker_model)
        return embedder, reranker
    except Exception as e:
        print(f"  sentence-transformers unavailable ({e}). Using TF-IDF fallback.")
        return None, None


class TfidfEmbedder:
    """
    Fallback embedder using TF-IDF when sentence-transformers
    models cannot be downloaded (e.g., restricted network).
    In production, swap this for SentenceTransformer.
    """
    def __init__(self):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vectorizer = TfidfVectorizer(max_features=512, stop_words="english")
        self.dim = 512
        self._fitted = False

    def fit(self, texts):
        self.vectorizer.fit(texts)
        self.dim = len(self.vectorizer.vocabulary_)
        self._fitted = True

    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        if not self._fitted:
            self.fit(texts)
        matrix = self.vectorizer.transform(texts).toarray().astype("float32")
        # Pad or truncate to fixed dimension
        target_dim = 512
        if matrix.shape[1] < target_dim:
            pad = np.zeros((matrix.shape[0], target_dim - matrix.shape[1]), dtype="float32")
            matrix = np.hstack([matrix, pad])
        elif matrix.shape[1] > target_dim:
            matrix = matrix[:, :target_dim]
        if normalize_embeddings:
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norms[norms == 0] = 1
            matrix = matrix / norms
        return matrix

    def get_sentence_embedding_dimension(self):
        return 512


class TfidfReranker:
    """
    Fallback reranker using keyword overlap scoring.
    In production, swap this for CrossEncoder.
    """
    def predict(self, pairs):
        scores = []
        for query, doc in pairs:
            q_words = set(query.lower().split())
            d_words = set(doc.lower().split())
            overlap = len(q_words & d_words)
            score = overlap / max(len(q_words), 1)
            scores.append(score)
        return scores


class FinSenseRAG:
    """
    Financial document RAG pipeline.

    Ingests invoices (PDF) and financial statements (CSV),
    chunks them with financial-awareness, embeds and indexes
    with FAISS, and retrieves with cross-encoder reranking.

    Uses sentence-transformers when available, falls back to
    TF-IDF for environments without HuggingFace access.
    In production, always use sentence-transformers.
    """

    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        index_path: str = None,
    ):
        print("Loading embedding model...")
        lightweight = os.getenv("LIGHTWEIGHT_MODE", "false").lower() == "true"

        if lightweight:
            print("  LIGHTWEIGHT_MODE=true: skipping sentence-transformers, using TF-IDF fallback.")
            st_embedder, st_reranker = None, None
        else:
            st_embedder, st_reranker = _load_sentence_transformers(embedding_model, reranker_model)

        if st_embedder:
            self.embedder = st_embedder
            self.reranker = st_reranker
            self.embed_dim = self.embedder.get_sentence_embedding_dimension()
            self.using_fallback = False
        else:
            print("  Using TF-IDF fallback embedder and keyword reranker.")
            self.embedder = TfidfEmbedder()
            self.reranker = TfidfReranker()
            self.embed_dim = 512
            self.using_fallback = True

        self.index = faiss.IndexFlatIP(self.embed_dim)
        self.chunks: List[dict] = []
        self.index_path = index_path

    def ingest_directory(self, data_dir: str):
        """
        Scan a directory for invoice PDFs and financial CSVs,
        parse them, chunk them, and add to the FAISS index.
        """
        print(f"\nIngesting documents from {data_dir}...")

        # Find all invoice PDFs
        invoice_dir = os.path.join(data_dir, "sample_invoices")
        pdf_files = sorted(glob.glob(os.path.join(invoice_dir, "*.pdf")))

        for pdf_path in pdf_files:
            parsed = extract_invoice_text(pdf_path)
            invoice_chunks = chunk_invoice(parsed)
            self.chunks.extend(invoice_chunks)
            print(f"  Indexed {os.path.basename(pdf_path)} ({len(invoice_chunks)} chunks)")

        # Find all financial CSVs
        fin_dir = os.path.join(data_dir, "sample_financials")
        csv_files = sorted(glob.glob(os.path.join(fin_dir, "*.csv")))

        for csv_path in csv_files:
            parsed = extract_csv_financials(csv_path)
            fin_chunks = chunk_financial_statement(parsed)
            self.chunks.extend(fin_chunks)
            print(f"  Indexed {os.path.basename(csv_path)} ({len(fin_chunks)} chunks)")

        # Build FAISS index
        self._build_index()
        print(f"\nTotal: {len(self.chunks)} chunks indexed in FAISS")

    def _build_index(self):
        """Embed all chunks and add to FAISS index."""
        if not self.chunks:
            return

        texts = [c["text"] for c in self.chunks]

        # TF-IDF fallback needs to fit on the corpus first
        if self.using_fallback:
            self.embedder.fit(texts)

        embeddings = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=not self.using_fallback)
        embeddings = np.array(embeddings, dtype="float32")

        self.embed_dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(self.embed_dim)
        self.index.add(embeddings)

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank_top_k: int = 5,
        client_filter: Optional[str] = None,
    ) -> List[dict]:
        """
        Retrieve relevant chunks for a query.

        1. FAISS nearest-neighbor search (fast, broad recall)
        2. Optional client filter (narrow to specific client)
        3. Cross-encoder reranking (precise relevance scoring)

        Returns the top rerank_top_k results with scores.
        """
        if self.index.ntotal == 0:
            return []

        # Step 1: Embed query and search FAISS
        query_vec = self.embedder.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype="float32")

        # Get more candidates than we need so filtering still leaves enough
        search_k = min(top_k * 3, self.index.ntotal)
        scores, indices = self.index.search(query_vec, search_k)

        candidates = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            chunk = self.chunks[idx].copy()
            chunk["faiss_score"] = float(score)
            candidates.append(chunk)

        # Step 2: Client filter (if specified)
        if client_filter:
            filter_lower = client_filter.lower()
            filtered = [
                c for c in candidates
                if filter_lower in c.get("metadata", {}).get("client", "").lower()
            ]
            # Fall back to unfiltered if filter removes everything
            if filtered:
                candidates = filtered

        # Step 3: Cross-encoder reranking
        if len(candidates) > 1:
            pairs = [(query, c["text"][:512]) for c in candidates[:top_k]]
            rerank_scores = self.reranker.predict(pairs)

            for i, score in enumerate(rerank_scores):
                candidates[i]["rerank_score"] = float(score)

            candidates.sort(key=lambda x: x.get("rerank_score", 0), reverse=True)

        return candidates[:rerank_top_k]

    def retrieve_text(
        self,
        query: str,
        top_k: int = 5,
        client_filter: Optional[str] = None,
    ) -> str:
        """
        Retrieve and format results as a single context string
        ready to pass to an LLM.
        """
        results = self.retrieve(query, top_k=10, rerank_top_k=top_k, client_filter=client_filter)

        if not results:
            return "No relevant documents found."

        context_parts = []
        for i, r in enumerate(results):
            source = r.get("metadata", {}).get("source", "unknown")
            score = r.get("rerank_score", r.get("faiss_score", 0))
            context_parts.append(
                f"--- Source {i+1}: {source} (relevance: {score:.3f}) ---\n{r['text']}\n"
            )

        return "\n".join(context_parts)
