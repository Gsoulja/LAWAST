"""
FastAPI application for LAWAST
Provides REST API endpoints compatible with OpenAI API format
"""

import os
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import uvicorn

from pydantic import BaseModel, Field

# Import pipeline
from ...pipeline.query_pipeline import QueryPipeline, PipelineConfig

# Initialize FastAPI app
app = FastAPI(
    title="LAWAST API",
    description="Swiss Legal AI Assistant API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global pipeline instance
pipeline: Optional[QueryPipeline] = None


# Pydantic models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Message role (user/assistant/system)")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="lawast", description="Model to use")
    messages: List[ChatMessage] = Field(..., description="Conversation messages")
    temperature: Optional[float] = Field(default=0.7, description="Temperature setting")
    max_tokens: Optional[int] = Field(default=2000, description="Maximum tokens")
    stream: Optional[bool] = Field(default=False, description="Stream response")
    session_id: Optional[str] = Field(default=None, description="Session ID for multi-turn")


class ChatCompletionResponse(BaseModel):
    id: str = Field(..., description="Unique response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(..., description="Creation timestamp")
    model: str = Field(..., description="Model used")
    choices: List[Dict[str, Any]] = Field(..., description="Response choices")
    usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage")


class QueryRequest(BaseModel):
    query: str = Field(..., description="User query")
    session_id: Optional[str] = Field(default=None, description="Session ID")
    include_citations: Optional[bool] = Field(default=True)
    include_confidence: Optional[bool] = Field(default=True)


class QueryResponse(BaseModel):
    answer: str = Field(..., description="Answer to the query")
    confidence: Optional[float] = Field(None, description="Confidence score")
    citations: Optional[List[Dict[str, Any]]] = Field(None, description="Sources")
    session_id: Optional[str] = Field(None, description="Session ID")
    execution_time: Optional[float] = Field(None, description="Processing time")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    timestamp: str = Field(..., description="Current timestamp")
    components: Dict[str, Any] = Field(..., description="Component statuses")


@app.on_event("startup")
async def startup_event():
    """Initialize pipeline on startup"""
    global pipeline

    # Set environment variables
    if api_key := os.getenv("HUGGINGFACE_API_KEY"):
        os.environ['HUGGINGFACE_API_KEY'] = api_key

    # Create pipeline configuration
    config = PipelineConfig(
        enable_agent=True,
        enable_rag=True,
        enable_reasoning=True,
        enable_articulation=True,
        enable_graceful_degradation=True,
        enable_monitoring=True,
        include_citations=True,
        include_confidence=True
    )

    # Initialize pipeline
    pipeline = QueryPipeline(config)
    print("✅ LAWAST pipeline initialized")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global pipeline
    if pipeline:
        # Cleanup if needed
        pass
    print("Pipeline shutdown complete")


@app.get("/", tags=["General"])
async def root():
    """Root endpoint"""
    return {
        "name": "LAWAST API",
        "version": "1.0.0",
        "description": "Swiss Legal AI Assistant",
        "endpoints": {
            "chat": "/v1/chat/completions",
            "query": "/v1/query",
            "health": "/health",
            "docs": "/docs"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        health = await pipeline.health_check()
        return HealthResponse(
            status=health["status"],
            timestamp=datetime.utcnow().isoformat(),
            components=health["components"]
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse, tags=["Chat"])
async def chat_completion(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint.
    This is what OpenWebUI can connect to.
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        # Extract the last user message
        user_message = request.messages[-1].content

        # Check if this is a metadata/utility request from OpenWebUI
        is_metadata_request = any([
            "### Task:" in user_message,
            "JSON format:" in user_message,
            "Generate a concise" in user_message,
            "Generate 1-3 broad tags" in user_message,
            "Suggest 3-5 relevant follow-up" in user_message
        ])

        if is_metadata_request:
            # Handle metadata requests directly with Apertus without legal pipeline
            print(f"📋 Handling OpenWebUI metadata request directly")

            # Use simple LLM response for these requests
            from ...articulation.apertus_client import ApertusChatClient
            client = ApertusChatClient()

            response_text = client.chat(
                message=user_message,
                max_tokens=200,
                temperature=request.temperature
            )

            # Return in OpenAI format
            response = ChatCompletionResponse(
                id=f"chatcmpl-metadata",
                created=int(datetime.utcnow().timestamp()),
                model=request.model,
                choices=[{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    },
                    "finish_reason": "stop"
                }],
                usage={
                    "prompt_tokens": len(user_message.split()),
                    "completion_tokens": len(response_text.split()),
                    "total_tokens": len(user_message.split()) + len(response_text.split())
                }
            )
            return response

        print(f"\n{'='*60}")
        print(f"📥 INCOMING REQUEST from OpenWebUI")
        print(f"{'='*60}")
        print(f"Model: {request.model}")
        print(f"Query: {user_message[:100]}...")  # Truncate long queries
        print(f"Session ID: {request.session_id or 'None'}")
        print(f"Temperature: {request.temperature}")
        print(f"{'='*60}\n")

        # Execute pipeline for actual legal queries
        if request.session_id:
            print(f"🔄 Processing with session: {request.session_id}")
            result = await pipeline.process_with_session(user_message, request.session_id)
        else:
            print(f"🚀 Executing new query...")
            result = await pipeline.execute(user_message)

        print(f"\n{'='*60}")
        print(f"✅ PIPELINE EXECUTION COMPLETE")
        print(f"{'='*60}")
        print(f"Answer length: {len(result.answer)} chars")
        print(f"Confidence: {result.confidence}")
        print(f"Citations: {len(result.citations) if result.citations else 0}")
        print(f"Execution time: {result.execution_time:.2f}s")
        print(f"Trace ID: {result.trace_id}")
        print(f"{'='*60}\n")

        # For OpenWebUI integration, we'll return clean answer without duplicating citations/confidence
        # The pipeline already includes citations and confidence in the structured result

        # Add court decision links if available
        if hasattr(result, 'court_decisions') and result.court_decisions:
            from .court_decision_formatter import CourtDecisionFormatter
            formatter = CourtDecisionFormatter()

            # For markdown-aware clients like OpenWebUI
            court_decision_text = formatter.format_for_markdown(result.court_decisions)

            # Append formatted court decisions to answer if not already included
            if "Relevant Court Decisions" not in result.answer:
                result.answer += court_decision_text

        # Format response in OpenAI format (keeping answer clean)
        response = ChatCompletionResponse(
            id=f"chatcmpl-{result.trace_id or 'unknown'}",
            created=int(datetime.utcnow().timestamp()),
            model=request.model,
            choices=[{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result.answer  # Clean answer without appended citations
                },
                "finish_reason": "stop"
            }],
            usage={
                "prompt_tokens": len(user_message.split()),
                "completion_tokens": len(result.answer.split()),
                "total_tokens": len(user_message.split()) + len(result.answer.split())
            }
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/query", response_model=QueryResponse, tags=["Query"])
async def direct_query(request: QueryRequest):
    """
    Direct query endpoint with full response details.
    """
    if not pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    try:
        # Execute pipeline
        if request.session_id:
            result = await pipeline.process_with_session(request.query, request.session_id)
        else:
            result = await pipeline.execute(request.query)

        # Format response
        response = QueryResponse(
            answer=result.answer,
            confidence=result.confidence if request.include_confidence else None,
            citations=[
                {
                    "source": c.source if hasattr(c, 'source') else str(c),
                    "reference": c.reference if hasattr(c, 'reference') else None,
                    "relevance": c.relevance if hasattr(c, 'relevance') else None
                }
                for c in result.citations
            ] if request.include_citations and result.citations else None,
            session_id=result.session_id,
            execution_time=result.execution_time
        )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models", tags=["Models"])
async def list_models():
    """List available models (OpenAI-compatible)"""
    return {
        "data": [
            {
                "id": "lawast",
                "object": "model",
                "created": int(datetime.utcnow().timestamp()),
                "owned_by": "lawast",
                "permission": [],
                "root": "lawast",
                "parent": None
            }
        ],
        "object": "list"
    }


@app.get("/metrics", tags=["Monitoring"])
async def get_metrics():
    """Get performance metrics"""
    if not pipeline or not pipeline.monitor:
        return {"message": "Metrics not available"}

    metrics = pipeline.monitor.get_all_metrics()
    return metrics


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server"""
    uvicorn.run(
        "src.interfaces.api.app:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()