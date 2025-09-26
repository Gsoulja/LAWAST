"""
Error handling and graceful degradation for pipeline
"""

import logging
import traceback
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """Severity levels for pipeline errors"""
    LOW = "low"        # Can continue with degraded functionality
    MEDIUM = "medium"  # Some features unavailable
    HIGH = "high"      # Major functionality impaired
    CRITICAL = "critical"  # Pipeline cannot continue


class PipelineError(Exception):
    """Base exception for pipeline errors"""
    def __init__(self,
                message: str,
                severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                stage: Optional[str] = None,
                cause: Optional[Exception] = None):
        super().__init__(message)
        self.severity = severity
        self.stage = stage
        self.cause = cause


class ComponentError(PipelineError):
    """Error in a pipeline component"""
    pass


class ConfigurationError(PipelineError):
    """Configuration related error"""
    def __init__(self, message: str):
        super().__init__(message, severity=ErrorSeverity.CRITICAL)


class TimeoutError(PipelineError):
    """Operation timeout error"""
    def __init__(self, message: str, stage: Optional[str] = None):
        super().__init__(message, severity=ErrorSeverity.HIGH, stage=stage)


@dataclass
class ErrorContext:
    """Context information for error handling"""
    error: Exception
    stage: Optional[str]
    query: Optional[str]
    trace_id: Optional[str]
    additional_info: Dict[str, Any]


@dataclass
class FallbackStrategy:
    """Defines a fallback strategy for error recovery"""
    name: str
    applicable_errors: List[Type[Exception]]
    severity_threshold: ErrorSeverity
    handler: callable
    description: str


class ErrorHandler:
    """
    Handles errors in the pipeline with graceful degradation strategies.
    """

    def __init__(self, enable_graceful_degradation: bool = True):
        """
        Initialize error handler.

        Args:
            enable_graceful_degradation: Enable fallback strategies
        """
        self.enable_graceful_degradation = enable_graceful_degradation
        self.fallback_strategies: List[FallbackStrategy] = []
        self.error_history: List[ErrorContext] = []
        self.max_error_history = 100

        # Register default fallback strategies
        if enable_graceful_degradation:
            self._register_default_strategies()

    def _register_default_strategies(self):
        """Register default fallback strategies"""
        # RAG failure fallback
        self.register_fallback(
            FallbackStrategy(
                name="rag_fallback",
                applicable_errors=[ComponentError],
                severity_threshold=ErrorSeverity.MEDIUM,
                handler=self._rag_fallback_handler,
                description="Use cached results or simple search when RAG fails"
            )
        )

        # Reasoning failure fallback
        self.register_fallback(
            FallbackStrategy(
                name="reasoning_fallback",
                applicable_errors=[ComponentError, TimeoutError],
                severity_threshold=ErrorSeverity.MEDIUM,
                handler=self._reasoning_fallback_handler,
                description="Return raw search results when reasoning fails"
            )
        )

        # Articulation failure fallback
        self.register_fallback(
            FallbackStrategy(
                name="articulation_fallback",
                applicable_errors=[ComponentError, TimeoutError],
                severity_threshold=ErrorSeverity.LOW,
                handler=self._articulation_fallback_handler,
                description="Use simple template-based response when articulation fails"
            )
        )

    def register_fallback(self, strategy: FallbackStrategy):
        """
        Register a fallback strategy.

        Args:
            strategy: Fallback strategy to register
        """
        self.fallback_strategies.append(strategy)
        logger.info(f"Registered fallback strategy: {strategy.name}")

    def handle_error(self, context: ErrorContext) -> Optional[Any]:
        """
        Handle an error with appropriate fallback strategy.

        Args:
            context: Error context information

        Returns:
            Fallback result or None
        """
        # Log error
        self._log_error(context)

        # Store in history
        self._store_error(context)

        # If graceful degradation is disabled, re-raise
        if not self.enable_graceful_degradation:
            raise context.error

        # Find applicable fallback strategy
        fallback = self._find_fallback_strategy(context)

        if fallback:
            logger.info(
                f"Applying fallback strategy '{fallback.name}' for {type(context.error).__name__}"
            )
            try:
                result = fallback.handler(context)
                return result
            except Exception as e:
                logger.error(f"Fallback strategy '{fallback.name}' failed: {str(e)}")
                # Try next fallback or raise
                pass

        # No fallback available, raise original error
        raise context.error

    def _find_fallback_strategy(self, context: ErrorContext) -> Optional[FallbackStrategy]:
        """
        Find applicable fallback strategy for the error.

        Args:
            context: Error context

        Returns:
            Applicable fallback strategy or None
        """
        error_type = type(context.error)
        severity = self._determine_severity(context.error)

        for strategy in self.fallback_strategies:
            # Check if error type matches
            type_match = any(
                issubclass(error_type, err_type)
                for err_type in strategy.applicable_errors
            )

            # Check if severity allows fallback
            severity_ok = (
                severity.value <= strategy.severity_threshold.value
                if hasattr(severity, 'value') else True
            )

            if type_match and severity_ok:
                return strategy

        return None

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """
        Determine the severity of an error.

        Args:
            error: The error to assess

        Returns:
            Error severity
        """
        if isinstance(error, PipelineError):
            return error.severity

        # Default severities for common errors
        if isinstance(error, TimeoutError):
            return ErrorSeverity.HIGH
        elif isinstance(error, ConnectionError):
            return ErrorSeverity.CRITICAL
        elif isinstance(error, ValueError):
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.MEDIUM

    def _log_error(self, context: ErrorContext):
        """Log error with context"""
        error_msg = f"Pipeline error in stage '{context.stage}': {str(context.error)}"

        if context.trace_id:
            error_msg = f"[{context.trace_id}] {error_msg}"

        # Log based on severity
        severity = self._determine_severity(context.error)
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(error_msg)
        elif severity == ErrorSeverity.HIGH:
            logger.error(error_msg)
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(error_msg)
        else:
            logger.info(error_msg)

        # Log traceback for unexpected errors
        if not isinstance(context.error, PipelineError):
            logger.debug(f"Traceback:\n{traceback.format_exc()}")

    def _store_error(self, context: ErrorContext):
        """Store error in history"""
        self.error_history.append(context)

        # Limit history size
        if len(self.error_history) > self.max_error_history:
            self.error_history = self.error_history[-self.max_error_history:]

    def _rag_fallback_handler(self, context: ErrorContext) -> Any:
        """Fallback handler for RAG failures"""
        logger.info("Using RAG fallback: returning empty results")
        return [], None  # Empty results, no metrics

    def _reasoning_fallback_handler(self, context: ErrorContext) -> Any:
        """Fallback handler for reasoning failures"""
        logger.info("Using reasoning fallback: creating simple response")
        # Create a simple reasoned answer without complex logic
        from ..reasoning.models import ReasonedAnswer, Citation
        return ReasonedAnswer(
            answer="I encountered an issue processing your request. Please try rephrasing.",
            confidence=0.1,
            citations=[],
            reasoning_steps=[]
        )

    def _articulation_fallback_handler(self, context: ErrorContext) -> str:
        """Fallback handler for articulation failures"""
        logger.info("Using articulation fallback: template response")
        if context.query:
            return f"I found some information related to '{context.query}' but couldn't generate a complete answer."
        else:
            return "I encountered an issue generating the response."

    def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics from history.

        Returns:
            Dictionary with error statistics
        """
        if not self.error_history:
            return {
                "total_errors": 0,
                "by_stage": {},
                "by_type": {},
                "by_severity": {}
            }

        stats = {
            "total_errors": len(self.error_history),
            "by_stage": {},
            "by_type": {},
            "by_severity": {}
        }

        for context in self.error_history:
            # Count by stage
            stage = context.stage or "unknown"
            stats["by_stage"][stage] = stats["by_stage"].get(stage, 0) + 1

            # Count by error type
            error_type = type(context.error).__name__
            stats["by_type"][error_type] = stats["by_type"].get(error_type, 0) + 1

            # Count by severity
            severity = self._determine_severity(context.error).value
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

        return stats

    def clear_error_history(self):
        """Clear error history"""
        self.error_history = []
        logger.info("Error history cleared")

    def create_error_report(self) -> str:
        """
        Create a human-readable error report.

        Returns:
            Error report as string
        """
        stats = self.get_error_statistics()

        report = "Pipeline Error Report\n"
        report += "=" * 50 + "\n\n"
        report += f"Total Errors: {stats['total_errors']}\n\n"

        if stats['total_errors'] > 0:
            report += "Errors by Stage:\n"
            for stage, count in stats['by_stage'].items():
                report += f"  {stage}: {count}\n"

            report += "\nErrors by Type:\n"
            for error_type, count in stats['by_type'].items():
                report += f"  {error_type}: {count}\n"

            report += "\nErrors by Severity:\n"
            for severity, count in stats['by_severity'].items():
                report += f"  {severity}: {count}\n"

            # Recent errors
            report += "\nRecent Errors (last 5):\n"
            for context in self.error_history[-5:]:
                report += f"  - [{context.stage}] {type(context.error).__name__}: {str(context.error)[:50]}...\n"

        return report