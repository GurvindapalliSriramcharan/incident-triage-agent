import hashlib
import logging
from typing import Any, Dict, List, Optional
from app.config import settings
from app.db.repositories import IncidentDocRepository

logger = logging.getLogger(__name__)

# Lazy singleton for GoogleGenerativeAIEmbeddings
_embeddings_client = None
_warned_no_key: bool = False


def get_embeddings_client():
    """Get or initialize the Google Generative AI embeddings client."""
    global _embeddings_client, _warned_no_key
    if _embeddings_client is not None:
        return _embeddings_client

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        if not _warned_no_key:
            logger.warning("GEMINI_API_KEY not set. Using offline deterministic embedding provider.")
            _warned_no_key = True
        return None

    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        # Adapt legacy or deprecated model names to active Gemini embedding model
        model_name = settings.GEMINI_EMBEDDING_MODEL
        if "text-embedding-004" in model_name:
            model_name = "models/gemini-embedding-001"

        _embeddings_client = GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=api_key,
            output_dimensionality=768,
            max_retries=1
        )
        logger.info(f"Initialized GoogleGenerativeAIEmbeddings with model: {model_name} (768 dimensions)")
        return _embeddings_client
    except Exception as e:
        logger.error(f"Could not initialize GoogleGenerativeAIEmbeddings: {e}")
        return None


def generate_embedding(text: str) -> List[float]:
    """
    Generate a 768-dimensional embedding vector for the given text.
    Uses Gemini embeddings when configured. In production, raises on failure rather than faking.
    """
    client = get_embeddings_client()
    if client is not None:
        try:
            vector = client.embed_query(text)
            if len(vector) > 768:
                return vector[:768]
            elif len(vector) < 768:
                return vector + [0.0] * (768 - len(vector))
            return vector
        except Exception as e:
            logger.error(f"Gemini embeddings API call failed: {e}")
            if settings.APP_ENV == "production":
                raise RuntimeError(f"Gemini embeddings service failure in production: {e}") from e
            logger.warning("Falling back to deterministic offline embedding for non-production environment.")

    # Fallback embedding generation for offline tests & environments where GEMINI_API_KEY is not set
    return _generate_deterministic_vector(text, dim=768)


def _generate_deterministic_vector(text: str, dim: int = 768) -> List[float]:
    """
    Generate a normalized deterministic vector based on text content and tokens.
    Guarantees consistent cosine similarity behavior during offline testing.
    """
    words = [w.lower().strip() for w in text.split() if w.strip()]
    vector = [0.0] * dim

    for i, word in enumerate(words):
        # Hash each word to distribute weight across vector dimensions
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vector[idx] += 1.0 / (1.0 + (i * 0.1))

    # Also add overall text hash fingerprint
    text_hash = hashlib.sha256(text.encode("utf-8")).digest()
    for i, byte_val in enumerate(text_hash):
        vector[i % dim] += (byte_val / 255.0)

    # L2 normalize
    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        vector = [round(x / norm, 6) for x in vector]
    return vector


def search_runbooks(
    query: str,
    service: Optional[str] = None,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Search internal runbook chunks using semantic vector similarity.
    Filters by service if specified.
    """
    if not query or not query.strip():
        return []

    query_embedding = generate_embedding(query)
    results = IncidentDocRepository.similarity_search(
        query_embedding=query_embedding,
        service=service,
        top_k=top_k
    )
    return results
