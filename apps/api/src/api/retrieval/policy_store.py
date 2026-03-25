import os
import logging
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class PolicyStore:
    """Loads policy markdown files and provides TF-IDF based retrieval."""

    def __init__(self, policies_dir: str):
        self.policies_dir = Path(policies_dir)
        self.documents: list[dict] = []
        self.vectorizer = TfidfVectorizer(stop_words="english")
        self.tfidf_matrix = None
        self._load_documents()

    def _load_documents(self):
        if not self.policies_dir.exists():
            logger.warning(f"Policies directory not found: {self.policies_dir}")
            return

        for filepath in sorted(self.policies_dir.glob("*.md")):
            content = filepath.read_text(encoding="utf-8")
            title = self._extract_title(content, filepath.stem)
            self.documents.append({
                "filename": filepath.name,
                "title": title,
                "content": content,
            })

        if self.documents:
            corpus = [doc["content"] for doc in self.documents]
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
            logger.info(f"Loaded {len(self.documents)} policy documents")
        else:
            logger.warning("No policy documents found")

    def _extract_title(self, content: str, fallback: str) -> str:
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
        return fallback.replace("-", " ").title()

    def search(self, query: str, top_k: int = 3, min_score: float = 0.05) -> list[dict]:
        if not self.documents or self.tfidf_matrix is None:
            return []

        query_vector = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vector, self.tfidf_matrix).flatten()

        ranked_indices = similarities.argsort()[::-1][:top_k]

        results = []
        for idx in ranked_indices:
            score = similarities[idx]
            if score >= min_score:
                results.append({
                    "filename": self.documents[idx]["filename"],
                    "title": self.documents[idx]["title"],
                    "content": self.documents[idx]["content"],
                    "score": float(score),
                })

        return results

    def get_all_titles(self) -> list[str]:
        return [doc["title"] for doc in self.documents]

    def get_document_by_filename(self, filename: str) -> dict | None:
        for doc in self.documents:
            if doc["filename"] == filename:
                return doc
        return None

    def get_all_documents_context(self) -> str:
        return "\n\n---\n\n".join(
            f"## {doc['title']}\n{doc['content']}" for doc in self.documents
        )
