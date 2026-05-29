import os
import logging
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import httpx
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
import numpy as np
import json
from prometheus_fastapi_instrumentator import Instrumentator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Chat Service")
Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

# Qdrant client
QDRANT_HOST = os.environ.get("CHAT_SERVICE_QDRANT_HOST", os.environ.get("QDRANT_HOST", "localhost"))
QDRANT_PORT = int(os.environ.get("CHAT_SERVICE_QDRANT_PORT", os.environ.get("QDRANT_PORT", "6333")))
qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Ollama configuration
OLLAMA_URL = os.environ.get("CHAT_SERVICE_OLLAMA_URL", os.environ.get("OLLAMA_URL", "http://localhost:11434"))
OLLAMA_MODEL = os.environ.get("CHAT_SERVICE_OLLAMA_MODEL", os.environ.get("OLLAMA_MODEL", "llama3.2"))
MIN_SCORE_THRESHOLD = float(os.environ.get("CHAT_SERVICE_MIN_SCORE_THRESHOLD", "0.25"))
MAX_CONTEXT_CHARS = int(os.environ.get("CHAT_SERVICE_MAX_CONTEXT_CHARS", "6500"))

# Embedding model (same as RAG indexer)
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384

logger.info(f"Loading sentence transformer model: {EMBEDDING_MODEL_NAME}")
try:
    embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)
    logger.info("Successfully loaded sentence transformer model")
except Exception as e:
    logger.error(f"Failed to load sentence transformer model: {e}")
    raise

class ChatRequest(BaseModel):
    question: str
    collection: str
    max_results: Optional[int] = 5

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    question: str

def search_qdrant(collection: str, query: str, max_results: int = 5):
    """Search Qdrant collection for relevant documents using vector search"""
    try:
        # Generate embedding for the query
        query_embedding = embedder.encode([query])[0]
        
        # Search in Qdrant
        search_result = qdrant.search(
            collection_name=collection,
            query_vector=query_embedding.tolist(),
            limit=max_results,
            with_payload=True,
            with_vectors=False
        )
        
        # Format results
        relevant_results = []
        for point in search_result:
            if point.score is None or point.score < MIN_SCORE_THRESHOLD:
                continue
            relevant_results.append({
                "text": point.payload.get("text", ""),
                "video_id": point.payload.get("video_id", ""),
                "title": point.payload.get("title", ""),
                "chunk_index": point.payload.get("chunk_index", 0),
                "score": point.score
            })
        
        return relevant_results
    
    except Exception as e:
        logger.error(f"Error searching Qdrant: {e}")
        return []

async def generate_response_with_ollama(question: str, context: List[dict]) -> str:
    """Generate response using Ollama"""
    try:
        ranked_context = sorted(context, key=lambda item: item.get("score", 0), reverse=True)
        packed_sources = []
        total_chars = 0
        for i, item in enumerate(ranked_context):
            block = f"Source {i+1} (Video: {item['title']}, Score: {item['score']:.3f}):\n{item['text']}"
            if total_chars + len(block) > MAX_CONTEXT_CHARS:
                break
            packed_sources.append(block)
            total_chars += len(block)

        context_text = "\n\n".join(packed_sources)

        prompt = f"""You are a helpful assistant that provides clear, concise answers based on the provided context. 
Your task is to synthesize the information and provide a natural, readable response that directly answers the question.

IMPORTANT CONTEXT ABOUT THE SHOW:
You are analyzing transcripts from "Batem Palma", a Romanian game show broadcast by Pro TV and hosted by Cosmin Seleși. Here's how the show works:

GAME OVERVIEW:
- Each episode features ONE main contestant who must open 24 mysterious boxes
- Each box contains money amounts ranging from 1 ban (0.01 lei) to 100,000 lei
- The contestant's goal is to eliminate as many "red amounts" (1 ban - 900 lei) as possible
- The Bank makes offers throughout the game - the contestant can "beat the palm" (accept an offer) at any time
- If they accept an offer, the game ends and they win that amount

GAME STRUCTURE (8 Rounds):
- Round 1: Open 6 boxes → First Bank offer
- Round 2: Open 4 boxes → Second Bank offer  
- Round 3: Open 3 boxes → Third Bank offer
- Round 4: Open 3 boxes → Fourth Bank offer
- Round 5: Open 3 boxes → Fifth Bank offer
- Round 6: Open 2 boxes → Sixth Bank offer
- Round 7: Open 1 box → Seventh Bank offer (final)
- Round 8: Open 2 boxes → Contestant leaves with remaining amount

KEY ELEMENTS:
- "Red amounts" (1 ban - 900 lei): Contestant wants to eliminate these
- "Yellow amounts" (1,000 - 100,000 lei): Contestant wants to keep these
- The Bank makes higher offers when more red amounts are eliminated
- The Bank makes lower offers when more yellow amounts are eliminated
- Eugenia Bobe (lawyer) is the only one who knows the amounts in boxes
- "Ce-ar fi fost dacă" (What if) - simulation if contestant hadn't accepted offer

When analyzing the transcripts, keep in mind:
- Identify the main contestant and their strategy
- Understand the tension between accepting Bank offers vs. continuing
- Recognize the psychological pressure of the game
- Consider the mathematical strategy of eliminating red vs. yellow amounts
- Pay attention to the Bank's offer calculations and timing

Context from the transcripts:
{context_text}

Question: {question}

Answer:"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60.0
            )

            if response.status_code != 200:
                logger.error(f"Ollama returned HTTP {response.status_code}: {response.text}")
                return "Sorry, there was an error generating the response (model error)."

            try:
                response_json = response.json()
            except Exception as e:
                logger.error(f"Failed to parse Ollama response JSON: {e}")
                logger.error(f"Raw response: {response.text}")
                return "Sorry, there was an error parsing the model's response."

            if "response" not in response_json:
                logger.error(f"Missing 'response' in Ollama output: {response_json}")
                return "Sorry, the model did not return a valid answer."

            return response_json["response"].strip()

    except Exception as e:
        logger.error(f"Unexpected error calling Ollama: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return f"Sorry, there was an error contacting the language model: {str(e)}"

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        logger.info(f"Processing chat request for collection: {req.collection}")
        
        # Check if collection exists
        collections = qdrant.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if req.collection not in collection_names:
            raise HTTPException(
                status_code=404, 
                detail=f"Collection '{req.collection}' not found. Available collections: {collection_names}"
            )
        
        # Search for relevant documents
        search_results = search_qdrant(req.collection, req.question, req.max_results)
        
        if not search_results:
            return ChatResponse(
                answer="I couldn't find any relevant information in the knowledge base to answer your question.",
                sources=[],
                question=req.question
            )
        
        # Generate response using Ollama
        answer = await generate_response_with_ollama(req.question, search_results)
        
        # Prepare sources
        sources = [
            {
                "video_id": result["video_id"],
                "title": result["title"],
                "chunk_index": result["chunk_index"],
                "score": result["score"],
                "text_preview": result["text"][:200] + "..." if len(result["text"]) > 200 else result["text"]
            }
            for result in search_results
        ]
        
        return ChatResponse(
            answer=answer,
            sources=sources,
            question=req.question
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collections")
async def list_collections():
    """List available Qdrant collections"""
    try:
        collections = qdrant.get_collections()
        return {
            "collections": [
                {
                    "name": col.name,
                    "points_count": col.points_count
                }
                for col in collections.collections
            ]
        }
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Qdrant connection
        collections = qdrant.get_collections()
        
        # Check embedding model
        test_embedding = embedder.encode(["test"])
        
        # Check Ollama connection
        async with httpx.AsyncClient() as client:
            ollama_response = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_healthy = ollama_response.status_code == 200
        
        return {
            "status": "healthy",
            "qdrant_connected": True,
            "qdrant_collections": len(collections.collections),
            "qdrant_host": QDRANT_HOST,
            "qdrant_port": QDRANT_PORT,
            "embedding_model": EMBEDDING_MODEL_NAME,
            "embedding_size": len(test_embedding[0]),
            "ollama_connected": ollama_healthy,
            "ollama_model": OLLAMA_MODEL
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006) 