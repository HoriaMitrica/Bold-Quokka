import os
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List
import httpx
from sentence_transformers import SentenceTransformer
import nltk
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct
import uuid

nltk.download('punkt_tab')

app = FastAPI(title="RAG Indexer Service")

# Qdrant client (assumes local Qdrant)
qdrant = QdrantClient(host="localhost", port=6333)

# Embedding model
embedder = SentenceTransformer("all-MiniLM-L6-v2")

# DB service URL (adjust as needed)
DB_SERVICE_URL = os.environ.get("DB_SERVICE_URL", "http://localhost:8001")
API_PREFIX = os.environ.get("API_PREFIX", "/api/v1")

class IndexRequest(BaseModel):
    text_file_path: str
    title: str
    video_id: str

class IndexByVideoIdRequest(BaseModel):
    video_id: str

@app.post("/index-text")
async def index_text(req: IndexRequest, space: str = Query(...)):
    # 1. Read file
    if not os.path.exists(req.text_file_path):
        raise HTTPException(status_code=404, detail="Text file not found")
    with open(req.text_file_path, encoding="utf-8") as f:
        text = f.read()
    # 2. Chunk text
    from nltk.tokenize import sent_tokenize
    sentences = sent_tokenize(text)
    chunk_size = 5  # sentences per chunk
    chunks = [" ".join(sentences[i:i+chunk_size]) for i in range(0, len(sentences), chunk_size)]
    # 3. Embed chunks
    embeddings = embedder.encode(chunks)
    # 4. Store in Qdrant
    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=emb.tolist(),
            payload={
                "video_id": req.video_id,
                "title": req.title,
                "chunk_index": idx,
                "text": chunk,
                "text_file_path": req.text_file_path
            }
        ))
    qdrant.upsert(collection_name=space, points=points)
    return {"status": "success", "chunks_indexed": len(points)}

@app.post("/index-by-video-id")
async def index_by_video_id(req: IndexByVideoIdRequest, space: str = Query(...)):
    # 1. Fetch text content info from db-service
    async with httpx.AsyncClient() as client:
        url = f"{DB_SERVICE_URL}{API_PREFIX}/text-contents/by-video/{req.video_id}"
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(status_code=404, detail=f"Text content for video_id {req.video_id} not found")
        data = resp.json()
        text_file_path = data.get("text_file_path")
        title = data.get("title")
        if not text_file_path or not os.path.exists(text_file_path):
            raise HTTPException(status_code=404, detail="Text file not found")
    # 2. Read file
    with open(text_file_path, encoding="utf-8") as f:
        text = f.read()
    # 3. Chunk text
    from nltk.tokenize import sent_tokenize
    sentences = sent_tokenize(text)
    chunk_size = 5
    chunks = [" ".join(sentences[i:i+chunk_size]) for i in range(0, len(sentences), chunk_size)]
    # 4. Embed chunks
    embeddings = embedder.encode(chunks)
    # 5. Store in Qdrant
    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=emb.tolist(),
            payload={
                "video_id": req.video_id,
                "title": title,
                "chunk_index": idx,
                "text": chunk,
                "text_file_path": text_file_path
            }
        ))
    qdrant.upsert(collection_name=space, points=points)
    return {"status": "success", "chunks_indexed": len(points)} 