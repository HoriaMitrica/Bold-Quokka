import os
import logging
import hashlib
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List
import httpx
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import (
    PointStruct,
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
)
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RAG Indexer Service")
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Qdrant configuration
QDRANT_HOST = os.environ.get("RAG_INDEXER_QDRANT_HOST", os.environ.get("QDRANT_HOST", "localhost"))
QDRANT_PORT = int(os.environ.get("RAG_INDEXER_QDRANT_PORT", os.environ.get("QDRANT_PORT", "6333")))
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Embedding model
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

logger.info(f"Loading sentence transformer model: {EMBEDDING_MODEL_NAME}")
try:
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Successfully loaded sentence transformer model")
except Exception as e:
    logger.error(f"Failed to load sentence transformer model: {e}")
    raise

# DB service URL
DB_SERVICE_URL = os.environ.get("RAG_INDEXER_DB_SERVICE_URL", os.environ.get("DB_SERVICE_URL", "http://localhost:8001"))
API_PREFIX = os.environ.get("RAG_INDEXER_API_PREFIX", os.environ.get("API_PREFIX", "/api/v1"))
MAX_CHUNK_TOKENS = int(os.environ.get("RAG_INDEXER_MAX_CHUNK_TOKENS", "350"))
CHUNK_OVERLAP_TOKENS = int(os.environ.get("RAG_INDEXER_CHUNK_OVERLAP_TOKENS", "60"))

class IndexRequest(BaseModel):
    text_file_path: str
    title: str
    video_id: str

class IndexByVideoIdRequest(BaseModel):
    video_id: str

def ensure_collection_exists(space: str):
    if space not in [col.name for col in qdrant.get_collections().collections]:
        logger.info(f"Creating Qdrant collection: {space}")
        qdrant.recreate_collection(
            collection_name=space,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
        )


def chunk_and_embed(text: str):
    # Approximate token-aware character size to keep prompt chunks stable.
    approx_chars_per_token = 4
    chunk_size_chars = MAX_CHUNK_TOKENS * approx_chars_per_token
    chunk_overlap_chars = CHUNK_OVERLAP_TOKENS * approx_chars_per_token

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size_chars,
        chunk_overlap=chunk_overlap_chars,
        separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ": ", " ", ""],
    )
    chunks = [chunk.strip() for chunk in splitter.split_text(text) if chunk.strip()]
    logger.info(f"Created {len(chunks)} context-preserving chunks")
    embeddings = embedder.encode(chunks)
    return chunks, embeddings

def _make_point_id(video_id: str, chunk_index: int, chunk_text: str) -> str:
    digest = hashlib.md5(f"{video_id}:{chunk_index}:{chunk_text}".encode("utf-8")).hexdigest()
    return digest


def upload_to_qdrant(space: str, video_id: str, title: str, text_file_path: str, chunks: List[str], embeddings: np.ndarray):
    ensure_collection_exists(space)
    qdrant.delete(
        collection_name=space,
        points_selector=Filter(
            must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]
        ),
    )
    points = [
        PointStruct(
            id=_make_point_id(video_id, idx, chunk),
            vector=emb.tolist(),
            payload={
                "video_id": video_id,
                "title": title,
                "chunk_index": idx,
                "text": chunk,
                "text_file_path": text_file_path,
                "embedding_model": EMBEDDING_MODEL_NAME,
            },
        )
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings))
    ]
    logger.info(f"Uploading {len(points)} points to Qdrant collection: {space}")
    qdrant.upload_points(collection_name=space, points=points)

@app.post("/index-text")
async def index_text(req: IndexRequest, space: str = Query(...)):
    try:
        if not os.path.exists(req.text_file_path):
            raise HTTPException(status_code=404, detail="Text file not found")

        with open(req.text_file_path, encoding="utf-8") as f:
            text = f.read()

        logger.info(f"Indexing text file for video: {req.video_id}")
        chunks, embeddings = chunk_and_embed(text)
        upload_to_qdrant(space, req.video_id, req.title, req.text_file_path, chunks, embeddings)

        return {"status": "success", "chunks_indexed": len(chunks)}

    except Exception as e:
        logger.error(f"Indexing failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index-by-video-id")
async def index_by_video_id(req: IndexByVideoIdRequest, space: str = Query(...)):
    try:
        url = f"{DB_SERVICE_URL}{API_PREFIX}/text-contents/by-video/{req.video_id}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise HTTPException(status_code=404, detail="Text content not found")
            data = resp.json()
            text_file_path = data.get("text_file_path")
            title = data.get("title")

        if not text_file_path or not os.path.exists(text_file_path):
            raise HTTPException(status_code=404, detail="Text file not found")

        with open(text_file_path, encoding="utf-8") as f:
            text = f.read()

        logger.info(f"Indexing text for video ID {req.video_id} (from DB service)")
        chunks, embeddings = chunk_and_embed(text)
        upload_to_qdrant(space, req.video_id, title, text_file_path, chunks, embeddings)

        return {"status": "success", "chunks_indexed": len(chunks)}

    except Exception as e:
        logger.error(f"Indexing by video ID failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    try:
        test_embedding = embedder.encode(["test"])
        collections = qdrant.get_collections()
        return {
            "status": "healthy",
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_size": len(test_embedding[0]),
            "qdrant_connected": True,
            "collections_count": len(collections.collections),
            "qdrant_host": QDRANT_HOST,
            "qdrant_port": QDRANT_PORT,
            "db_service_url": DB_SERVICE_URL,
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}
