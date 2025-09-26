"""
LAWAST Pipeline for OpenWebUI
This module provides a Pipeline class compatible with OpenWebUI's pipeline framework
"""

import os
import sys
import asyncio
import logging
from typing import List, Union, Generator, Iterator, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Pipeline:
    """
    OpenWebUI Pipeline implementation for LAWAST
    Integrates Swiss legal AI with OpenWebUI's RAG framework
    """

    class Valves:
        """Configuration valves for the pipeline"""
        def __init__(self):
            # Model configuration
            self.HUGGINGFACE_API_KEY: str = os.getenv("HUGGINGFACE_API_KEY", "")

            # Neo4j configuration
            self.NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            self.NEO4J_USER: str = os.getenv("NEO4J_USER", "neo4j")
            self.NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "lawast2024")

            # Pipeline configuration
            self.ENABLE_AGENT: bool = True
            self.ENABLE_RAG: bool = True
            self.ENABLE_REASONING: bool = True
            self.ENABLE_ARTICULATION: bool = True
            self.ENABLE_GRACEFUL_DEGRADATION: bool = True

            # Response configuration
            self.MAX_RESPONSE_LENGTH: int = 2000
            self.INCLUDE_CITATIONS: bool = True
            self.INCLUDE_CONFIDENCE: bool = True

            # Performance settings
            self.TIMEOUT_SECONDS: int = 30
            self.ENABLE_CACHING: bool = True

    def __init__(self):
        """Initialize the LAWAST pipeline"""
        self.valves = self.Valves()
        self.pipeline = None
        self.name = "LAWAST Swiss Legal AI"
        self.description = "Swiss legal question answering using LAWAST + Apertus"

        # Metadata for OpenWebUI
        self.version = "1.0.0"
        self.author = "LAWAST Team"
        self.license = "MIT"

    async def on_startup(self):
        """
        Called when the pipeline is started.
        Initialize components and connections.
        """
        logger.info("Starting LAWAST pipeline...")

        try:
            # Set environment variables from valves
            if self.valves.HUGGINGFACE_API_KEY:
                os.environ['HUGGINGFACE_API_KEY'] = self.valves.HUGGINGFACE_API_KEY

            # Import here to avoid loading issues
            from src.pipeline.query_pipeline import QueryPipeline, PipelineConfig

            # Create pipeline configuration
            config = PipelineConfig(
                enable_agent=self.valves.ENABLE_AGENT,
                enable_rag=self.valves.ENABLE_RAG,
                enable_reasoning=self.valves.ENABLE_REASONING,
                enable_articulation=self.valves.ENABLE_ARTICULATION,
                enable_graceful_degradation=self.valves.ENABLE_GRACEFUL_DEGRADATION,
                timeout_seconds=self.valves.TIMEOUT_SECONDS,
                enable_caching=self.valves.ENABLE_CACHING,
                max_response_length=self.valves.MAX_RESPONSE_LENGTH,
                include_citations=self.valves.INCLUDE_CITATIONS,
                include_confidence=self.valves.INCLUDE_CONFIDENCE
            )

            # Initialize the query pipeline
            self.pipeline = QueryPipeline(config)

            logger.info("LAWAST pipeline initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize LAWAST pipeline: {e}")
            raise

    async def on_shutdown(self):
        """
        Called when the pipeline is stopped.
        Clean up resources.
        """
        logger.info("Shutting down LAWAST pipeline...")

        if self.pipeline:
            # Close any connections
            try:
                # Pipeline cleanup if needed
                pass
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")

    def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: List[dict],
        body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Main pipeline execution method for OpenWebUI.

        Args:
            user_message: The user's query
            model_id: Model identifier (not used, we use Apertus)
            messages: Conversation history
            body: Additional request body parameters

        Returns:
            Response string or generator for streaming
        """
        logger.info(f"Processing query: {user_message[:100]}...")

        if not self.pipeline:
            return "Pipeline not initialized. Please check configuration."

        try:
            # Extract session ID if available
            session_id = body.get("session_id", None)

            # Check if streaming is requested
            stream = body.get("stream", False)

            # Run async pipeline in sync context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Execute pipeline
                result = loop.run_until_complete(
                    self._execute_pipeline(user_message, session_id, messages)
                )

                # Format response
                response = self._format_response(result)

                if stream:
                    # Return generator for streaming
                    return self._stream_response(response)
                else:
                    return response

            finally:
                loop.close()

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            return f"I encountered an error processing your request: {str(e)}"

    async def _execute_pipeline(
        self,
        query: str,
        session_id: str = None,
        messages: List[dict] = None
    ):
        """
        Execute the LAWAST pipeline.

        Args:
            query: User query
            session_id: Optional session ID for multi-turn dialogue
            messages: Conversation history

        Returns:
            Pipeline result
        """
        # Build context from message history if available
        context = {}
        if messages and len(messages) > 1:
            # Extract relevant context from previous messages
            context["history"] = [
                {"role": msg.get("role"), "content": msg.get("content")}
                for msg in messages[-5:]  # Keep last 5 messages for context
            ]

        # Execute pipeline
        if session_id:
            result = await self.pipeline.process_with_session(query, session_id)
        else:
            result = await self.pipeline.execute(query, context=context)

        return result

    def _format_response(self, result) -> str:
        """
        Format pipeline result for OpenWebUI.

        Args:
            result: Pipeline result object

        Returns:
            Formatted response string
        """
        response_parts = []

        # Main answer
        response_parts.append(result.answer)

        # Add citations if available
        if self.valves.INCLUDE_CITATIONS and result.citations:
            response_parts.append("\n\n**Sources:**")
            for i, citation in enumerate(result.citations[:5], 1):
                source = citation.source if hasattr(citation, 'source') else str(citation)
                response_parts.append(f"{i}. {source}")

        # Add confidence if requested
        if self.valves.INCLUDE_CONFIDENCE and result.confidence:
            response_parts.append(f"\n\n*Confidence: {result.confidence:.1%}*")

        # Add any warnings
        if result.warnings:
            response_parts.append(f"\n\n⚠️ {', '.join(result.warnings)}")

        return "\n".join(response_parts)

    def _stream_response(self, response: str) -> Generator[str, None, None]:
        """
        Stream response in chunks for OpenWebUI.

        Args:
            response: Complete response string

        Yields:
            Response chunks
        """
        # Split response into words for streaming
        words = response.split()

        for i, word in enumerate(words):
            if i > 0:
                yield " "
            yield word

            # Small delay for streaming effect
            import time
            time.sleep(0.01)

    async def get_status(self) -> Dict[str, Any]:
        """
        Get pipeline status for monitoring.

        Returns:
            Status dictionary
        """
        if not self.pipeline:
            return {"status": "not_initialized"}

        try:
            health = await self.pipeline.health_check()
            return {
                "status": "operational",
                "health": health,
                "version": self.version
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "version": self.version
            }


# OpenWebUI expects a Pipeline class at module level
__all__ = ['Pipeline']