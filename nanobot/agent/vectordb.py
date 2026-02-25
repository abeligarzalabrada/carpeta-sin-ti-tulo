import os
import re
import json
import math
from pathlib import Path
from loguru import logger

class LocalVectorDB:
    """A lightweight, pure-Python vector database using TF-IDF for zero dependencies.
    This guarantees 100% compatibility across Windows, Mac, and Linux without C++ tools.
    """
    def __init__(self, workspace: Path):
        self.db_path = workspace / "vector_memory"
        self.db_path.mkdir(exist_ok=True)
        self.index_file = self.db_path / "index.json"
        
        # In-memory storage: lists of dicts {"id", "session", "role", "content", "vector", "tokens"}
        self.documents = []
        self._load_index()
        logger.info("Native Pure-Python Vector DB initialized.")

    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    self.documents = json.load(f)
            except Exception:
                self.documents = []

    def _save_index(self):
        try:
            with open(self.index_file, "w", encoding="utf-8") as f:
                json.dump(self.documents, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save Vector DB index: {e}")

    def _tokenize(self, text: str) -> dict:
        """Simple tokenization and frequency count for TF vectors."""
        words = re.findall(r'\w+', text.lower())
        freq = {}
        for w in words:
            if len(w) > 2:  # ignore extremely short stop words roughly
                freq[w] = freq.get(w, 0) + 1
        return freq

    def _cosine_similarity(self, vec1: dict, vec2: dict) -> float:
        """Compute cosine similarity between two sparse vectors."""
        intersection = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[w] * vec2[w] for w in intersection)
        
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if not mag1 or not mag2:
            return 0.0
        return dot_product / (mag1 * mag2)

    def add_message(self, session_key: str, msg: dict, msg_idx: int):
        if not msg.get("content") or not isinstance(msg["content"], str):
            return
        content = msg["content"].strip()
        if not content:
            return
        
        doc_id = f"{session_key}_{msg_idx}"
        # Update if exists
        for d in self.documents:
            if d["id"] == doc_id:
                return  # already indexed
                
        vector = self._tokenize(content)
        if not vector:
            return
            
        self.documents.append({
            "id": doc_id,
            "session": session_key,
            "role": msg.get("role", "user"),
            "content": content,
            "vector": vector
        })
        self._save_index()

    def search_messages(self, session_key: str, query: str, top_k: int = 4) -> list[dict]:
        if not query or not query.strip() or not self.documents:
            return []
            
        query_vec = self._tokenize(query)
        if not query_vec:
            return []

        # Filter by session
        session_docs = [d for d in self.documents if d["session"] == session_key]
        
        scored_docs = []
        for doc in session_docs:
            score = self._cosine_similarity(query_vec, doc["vector"])
            if score > 0.05:  # Slight relevance threshold
                scored_docs.append((score, doc))
                
        # Sort by relevance descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Take top_k
        top_docs = scored_docs[:top_k]
        
        # Sort chronologically (by assuming id ends with integer index)
        # to feed LLM in a somewhat logical order
        top_docs.sort(key=lambda x: int(x[1]["id"].split("_")[-1]))
        
        messages = []
        for score, doc in top_docs:
            messages.append({
                "role": doc["role"], 
                "content": f"[From Past Context]: {doc['content']}",
                "is_from_vector": True
            })
        return messages
