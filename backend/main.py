from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import run_agent

app = FastAPI(title="School MVP Dashboard API")

# Configure CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str

@app.get("/")
def read_root():
    return {"message": "Welcome to the School MVP Dashboard API"}

@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Endpoint that handles the Agentic NL2SQL requests.
    """
    try:
        response_text = run_agent(request.query)
        return ChatResponse(response=response_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard-layout")
def get_dashboard_layout():
    """
    Placeholder for the AI Dashboard Evaluator.
    In the real implementation, an agent would fetch current DB metrics 
    and return an ordered array of widget IDs based on priority.
    """
    # For MVP, simulate AI evaluator behavior
    return {
        "layout": [
            "alerts_widget", 
            "unpaid_fees_widget", 
            "attendance_widget", 
            "grades_widget"
        ],
        "briefing": "Good morning Admin! We've noticed that 15 students have attendance below 75%, and there are several unpaid invoices. Please check the alerts widget."
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
