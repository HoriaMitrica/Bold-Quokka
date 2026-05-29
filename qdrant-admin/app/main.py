import os
from fastapi import FastAPI, HTTPException, Path, Query
from pydantic import BaseModel
from typing import List, Optional
from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, PointStruct
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Qdrant Admin API")

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

class CreateCollectionRequest(BaseModel):
    name: str
    vector_size: int
    distance: str = "Cosine"  # "Cosine", "Euclid", or "Dot"

class PointPayload(BaseModel):
    id: Optional[str]
    vector: List[float]
    payload: dict

@app.post("/collections")
def create_collection(req: CreateCollectionRequest):
    try:
        qdrant.recreate_collection(
            collection_name=req.name,
            vectors_config=VectorParams(size=req.vector_size, distance=req.distance)
        )
        return {"status": "created", "collection": req.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/collections/{collection_name}/points")
def add_points(collection_name: str, points: List[PointPayload]):
    try:
        qdrant.upsert(
            collection_name=collection_name,
            points=[
                PointStruct(
                    id=point.id,
                    vector=point.vector,
                    payload=point.payload
                ) for point in points
            ]
        )
        return {"status": "success", "points_added": len(points)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collections")
def list_collections():
    try:
        collections = qdrant.get_collections()
        return collections.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collections/{collection_name}/points")
def list_points(collection_name: str, limit: int = Query(10, ge=1, le=100)):
    try:
        scroll_result = qdrant.scroll(
            collection_name=collection_name,
            limit=limit
        )
        # Return points and next page offset if available
        return {
            "points": [point.dict() for point in scroll_result[0]],
            "next_offset": scroll_result[1]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 


@app.get("/health")
def health_check():
    try:
        collections = qdrant.get_collections()
        return {
            "status": "healthy",
            "qdrant_host": QDRANT_HOST,
            "qdrant_port": QDRANT_PORT,
            "collections_count": len(collections.collections),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}