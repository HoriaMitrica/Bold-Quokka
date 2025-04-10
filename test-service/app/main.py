from fastapi import FastAPI
import httpx

app = FastAPI(title="Test Service API")

@app.get("/")
async def root():
    return {"message": "Welcome to the Test Service API"}

@app.get("/test-main-api")
async def test_main_api():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://api:8000/health")
            return {
                "status": "success",
                "main_api_status": response.json()
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            } 