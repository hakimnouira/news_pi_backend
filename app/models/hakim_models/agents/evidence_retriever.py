from typing import List, Dict, Any, Tuple
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document



KB_PERSIST_DIR = "./knowledge_base/chroma_db"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
# Optional: for query expansion
DEFAULT_EXPANSION_PROMPTS = [
    "What is the core factual claim?",
    "Which named entities are present? (people, orgs, places)",
    "What timeframe is implied?",
    "Which alternative phrasings or synonyms could be used?",
]

class EvidenceRetrieverAgent:
    def __init__(self, k: int = 5, use_mmr: bool = True, lambda_mult: float = 0.5):
        # Initialize embedding model
        self.embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
        self.db = Chroma(
            persist_directory=KB_PERSIST_DIR,
            embedding_function=self.embeddings
        )
        # Keep params
        self.k = k
        self.use_mmr = use_mmr
        self.lambda_mult = lambda_mult

        # Expose both retriever and vectorstore for similarity scores
        self.retriever = self.db.as_retriever(
            search_kwargs={
                "k": self.k,
                "lambda_mult": self.lambda_mult,
            },
            search_type="mmr" if self.use_mmr else "similarity"
        )

    # --------- Explainability helpers ---------
    def _query_expansion(self, claim: str) -> List[str]:
        # Lightweight heuristic expansion (no LLM call for speed/cost)
        expansions = [claim]
        # naive token-based expansions; customize as needed
        if ":" in claim:
            expansions.append(claim.split(":", 1)[-1].strip())
        if "-" in claim:
            expansions.extend([p.strip() for p in claim.split("-") if p.strip()])
        if " says " in claim.lower():
            expansions.append(claim.lower().split(" says ", 1)[-1].strip())
        # Deduplicate and keep reasonably unique
        uniq = []
        for e in expansions:
            if e and e not in uniq and len(e.split()) > 2:
                uniq.append(e)
        return uniq[:3]  # keep top few

    def _score_docs(self, query: str, docs: List[Document]) -> List[Tuple[Document, float]]:
        """
        Compute cosine similarities between query and doc embeddings to expose scores.
        """
        q_emb = self.embeddings.embed_query(query)
        scored = []
        for d in docs:
            d_emb = d.metadata.get("_embedding")
            if d_emb is None:
                # compute and cache embedding on the fly
                d_emb = self.embeddings.embed_documents([d.page_content])[0]
                d.metadata["_embedding"] = d_emb
            # cosine similarity
            num = sum(q * x for q, x in zip(q_emb, d_emb))
            q_norm = (sum(q*q for q in q_emb)) ** 0.5
            d_norm = (sum(x*x for x in d_emb)) ** 0.5
            sim = 0.0 if q_norm == 0 or d_norm == 0 else num / (q_norm * d_norm)
            scored.append((d, sim))
        # sort by similarity desc
        return sorted(scored, key=lambda x: x[1], reverse=True)

    def _make_xai_bundle(
        self,
        claim: str,
        expansions: List[str],
        results: Dict[str, List[Tuple[Document, float]]],
        top_n: int
    ) -> Dict[str, Any]:
        """
        Build a compact XAI object: which queries were used, which docs matched,
        their scores, and normalized contribution weights.
        """
        # flatten all docs and track max sim per doc across expansions
        doc_entries = []
        seen = {}
        for q, pairs in results.items():
            for doc, sim in pairs[:top_n]:
                key = (doc.metadata.get("source") or "") + "|" + (doc.metadata.get("id") or doc.page_content[:60])
                if key not in seen or sim > seen[key]["similarity"]:
                    seen[key] = {
                        "query_variant": q,
                        "similarity": sim,
                        "doc": doc
                    }

        # Normalize similarities to weights 0..1 for interpretability
        sims = [v["similarity"] for v in seen.values()]
        if sims:
            min_s, max_s = min(sims), max(sims)
            rng = max(max_s - min_s, 1e-6)
            for v in seen.values():
                v["weight"] = (v["similarity"] - min_s) / rng
        else:
            for v in seen.values():
                v["weight"] = 0.0

        # rank by weight
        ranked = sorted(seen.values(), key=lambda x: x["weight"], reverse=True)

        # Build explainable items for API/frontend
        items = []
        for v in ranked[:top_n]:
            d = v["doc"]
            items.append({
                "source": d.metadata.get("source") or d.metadata.get("url") or "unknown",
                "title": d.metadata.get("title") or "untitled",
                "snippet": d.page_content[:350],
                "similarity": round(v["similarity"], 4),
                "weight": round(v["weight"], 4),
                "query_variant": v["query_variant"],
                "metadata": {k: d.metadata[k] for k in d.metadata if not k.startswith("_")}
            })

        return {
            "claim": claim,
            "query_variants": expansions,
            "retrieval_type": "mmr" if self.use_mmr else "similarity",
            "lambda_mult": self.lambda_mult,
            "selected_evidence": items
        }

    # --------- Main retrieval with XAI ---------
    def get_evidence(self, claim: str, max_docs: int = 3) -> List[Document]:
        # Preserve old signature behavior
        docs = self.retriever.invoke(claim)
        return docs[:max_docs] if docs else []

    def get_evidence_with_xai(self, claim: str, max_docs: int = 3) -> Dict[str, Any]:
        """
        Return an explainable retrieval bundle:
        - query variants (expansions)
        - top docs with similarity scores
        - normalized contribution weights
        """
        expansions = self._query_expansion(claim)
        expansions = expansions or [claim]

        # Collect results for each variant
        results: Dict[str, List[Tuple[Document, float]]] = {}
        for q in expansions:
            # use underlying vectorstore for raw docs (more control)
            if self.use_mmr:
                docs = self.db.max_marginal_relevance_search(q, k=self.k, lambda_mult=self.lambda_mult)
            else:
                docs = self.db.similarity_search(q, k=self.k)

            # score with explicit cosine sim (explainability)
            scored = self._score_docs(q, docs)
            results[q] = scored

        # build XAI object
        xai_bundle = self._make_xai_bundle(claim, expansions, results, top_n=max_docs)
        return xai_bundle
