"""
FinSense API Server.

REST endpoints for invoice Q&A, financial analysis,
and all the tools an airCFO accountant needs.

Start with: uvicorn app.main:app --reload
"""

import os
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from app.rag.pipeline import FinSenseRAG
from app.agents.invoice_agent import InvoiceAgent

app = FastAPI(
    title="FinSense",
    description=(
        "AI-powered invoice and financial document agent. "
        "Answers natural language questions about invoices, "
        "computes financial metrics, flags anomalies, and "
        "drafts professional client replies. Built for airCFO."
    ),
    version="1.0.0",
)

# Global instances (initialized on startup)
rag: Optional[FinSenseRAG] = None
agent: Optional[InvoiceAgent] = None


class QuestionRequest(BaseModel):
    question: str = Field(..., description="Natural language question about an invoice or financials")
    client_filter: Optional[str] = Field(None, description="Optional client name to narrow the search")


class QuestionResponse(BaseModel):
    answer: str
    sources: list
    draft_reply: Optional[str] = None
    metrics: Optional[dict] = None
    reasoning: list = []
    latency_ms: float = 0


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    client_filter: Optional[str] = None


@app.on_event("startup")
async def startup():
    """Load the RAG pipeline and index all documents on server start."""
    global rag, agent

    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

    rag = FinSenseRAG()
    rag.ingest_directory(data_dir)

    agent = InvoiceAgent(rag=rag, data_dir=data_dir)

    print("\nFinSense is ready. All documents indexed.")


@app.get("/")
async def root():
    return {
        "service": "FinSense",
        "version": "1.0.0",
        "description": "AI invoice and financial document agent for airCFO",
        "endpoints": {
            "/ask": "POST - Ask any question about invoices or financials",
            "/search": "POST - Raw document search",
            "/health": "GET - Health check",
            "/tools": "GET - List available MCP tools",
        },
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "documents_indexed": rag.index.ntotal if rag else 0,
        "chunks_loaded": len(rag.chunks) if rag else 0,
    }


@app.post("/ask", response_model=QuestionResponse)
async def ask_question(req: QuestionRequest):
    """
    Ask a natural language question about an invoice or financials.

    The agent will:
    1. Parse your question to understand what you need
    2. Retrieve relevant invoices and financial documents
    3. Calculate any needed metrics
    4. Draft a professional reply if appropriate

    Examples:
    - "Explain the $12,500 charge on GreenThread's February invoice"
    - "What is NovaByte's burn rate in Q1 vs Q2?"
    - "Flag anything unusual in NovaByte's March expenses"
    - "How much runway does PulseMetrics have?"
    """
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized yet")

    start = time.time()
    result = agent.answer(req.question)
    latency = (time.time() - start) * 1000

    return QuestionResponse(
        answer=result.get("answer", ""),
        sources=result.get("sources", []),
        draft_reply=result.get("draft_reply"),
        metrics=result.get("metrics"),
        reasoning=result.get("reasoning", []),
        latency_ms=round(latency, 1),
    )


@app.post("/search")
async def search_documents(req: SearchRequest):
    """Raw document search without agent reasoning. Returns retrieved chunks."""
    if not rag:
        raise HTTPException(status_code=503, detail="RAG not initialized yet")

    results = rag.retrieve(req.query, top_k=req.top_k * 2, rerank_top_k=req.top_k, client_filter=req.client_filter)

    return {
        "query": req.query,
        "results": [
            {
                "text": r["text"][:500],
                "metadata": r.get("metadata", {}),
                "score": r.get("rerank_score", r.get("faiss_score", 0)),
            }
            for r in results
        ],
    }


@app.get("/tools")
async def list_tools():
    """List all available tools (MCP tool descriptions)."""
    return {
        "tools": [
            {
                "name": "query_invoices",
                "description": "Search over all ingested invoices using natural language. Returns the most relevant invoice chunks with relevance scores.",
                "parameters": {"query": "string", "client_filter": "string (optional)"},
            },
            {
                "name": "calculate_metrics",
                "description": "Compute burn rate, runway, gross margin, and growth metrics for a client.",
                "parameters": {"client": "string", "metric": "burn_rate | runway | gross_margin"},
            },
            {
                "name": "compare_periods",
                "description": "Compare two time periods (e.g., Q1 vs Q2) for a client. Shows deltas and percentage changes for every expense category.",
                "parameters": {"client": "string", "period_1": "Q1 | Q2", "period_2": "Q1 | Q2"},
            },
            {
                "name": "flag_anomalies",
                "description": "Detect unusual month-over-month changes in expense categories. Flags spikes, drops, and new expenses.",
                "parameters": {"client": "string", "month": "string (optional)"},
            },
            {
                "name": "generate_analysis",
                "description": "Generate a CFO-level month-end analysis paragraph for a client and month.",
                "parameters": {"client": "string", "month": "string"},
            },
            {
                "name": "draft_reply",
                "description": "Draft a professional client-facing email reply to an invoice question.",
                "parameters": {"question": "string", "client_filter": "string (optional)"},
            },
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
