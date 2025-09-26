"""
Execution flow manager for pipeline stages
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class StageStatus(Enum):
    """Status of a pipeline stage"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageResult:
    """Result from a pipeline stage execution"""
    name: str
    status: StageStatus
    output: Optional[Any] = None
    error: Optional[Exception] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        """Check if stage was successful"""
        return self.status == StageStatus.COMPLETED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "name": self.name,
            "status": self.status.value,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "metadata": self.metadata,
            "error": str(self.error) if self.error else None
        }


@dataclass
class Stage:
    """Definition of a pipeline stage"""
    name: str
    function: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[str] = field(default_factory=list)
    optional: bool = False
    timeout: Optional[float] = None
    retry_on_failure: bool = False
    max_retries: int = 3


class ExecutionFlow:
    """
    Manages the execution flow of pipeline stages.
    Supports dependencies, parallel execution, and error handling.
    """

    def __init__(self, enable_parallel: bool = True):
        """
        Initialize execution flow manager.

        Args:
            enable_parallel: Enable parallel execution of independent stages
        """
        self.enable_parallel = enable_parallel
        self.stages: Dict[str, Stage] = {}
        self.results: Dict[str, StageResult] = {}

    def add_stage(self, stage: Stage):
        """
        Add a stage to the execution flow.

        Args:
            stage: Stage definition
        """
        if stage.name in self.stages:
            logger.warning(f"Stage {stage.name} already exists, overwriting")
        self.stages[stage.name] = stage
        logger.debug(f"Added stage: {stage.name}")

    def remove_stage(self, name: str):
        """
        Remove a stage from the execution flow.

        Args:
            name: Stage name to remove
        """
        if name in self.stages:
            del self.stages[name]
            logger.debug(f"Removed stage: {name}")

    async def execute(self,
                     skip_stages: Optional[List[str]] = None) -> Dict[str, StageResult]:
        """
        Execute all stages in the flow.

        Args:
            skip_stages: Optional list of stage names to skip

        Returns:
            Dictionary of stage results
        """
        skip_stages = skip_stages or []
        self.results = {}

        # Build execution order based on dependencies
        execution_order = self._build_execution_order()

        # Group stages for parallel execution
        stage_groups = self._group_stages_for_parallel(execution_order)

        # Execute stage groups
        for group in stage_groups:
            if self.enable_parallel and len(group) > 1:
                await self._execute_parallel(group, skip_stages)
            else:
                for stage_name in group:
                    await self._execute_stage(stage_name, skip_stages)

        return self.results

    def _build_execution_order(self) -> List[str]:
        """
        Build execution order based on dependencies using topological sort.

        Returns:
            Ordered list of stage names
        """
        # Build dependency graph
        graph = {name: set(stage.depends_on) for name, stage in self.stages.items()}

        # Topological sort
        visited = set()
        stack = []

        def visit(node):
            if node in visited:
                return
            visited.add(node)
            for dep in graph.get(node, []):
                if dep in graph:  # Only visit if dependency exists
                    visit(dep)
            stack.append(node)

        for node in graph:
            visit(node)

        return stack

    def _group_stages_for_parallel(self,
                                  execution_order: List[str]) -> List[List[str]]:
        """
        Group stages that can be executed in parallel.

        Args:
            execution_order: Ordered list of stage names

        Returns:
            List of stage groups
        """
        groups = []
        completed = set()

        remaining = execution_order.copy()
        while remaining:
            # Find stages that can run now
            current_group = []
            for stage_name in remaining[:]:
                stage = self.stages[stage_name]
                # Check if all dependencies are completed
                if all(dep in completed for dep in stage.depends_on):
                    current_group.append(stage_name)
                    remaining.remove(stage_name)

            if not current_group:
                # Circular dependency or missing stage
                logger.error(f"Cannot resolve dependencies for stages: {remaining}")
                break

            groups.append(current_group)
            completed.update(current_group)

        return groups

    async def _execute_stage(self,
                           stage_name: str,
                           skip_stages: List[str]) -> StageResult:
        """
        Execute a single stage.

        Args:
            stage_name: Name of stage to execute
            skip_stages: List of stages to skip

        Returns:
            Stage result
        """
        if stage_name in skip_stages:
            result = StageResult(
                name=stage_name,
                status=StageStatus.SKIPPED
            )
            self.results[stage_name] = result
            logger.info(f"Skipped stage: {stage_name}")
            return result

        stage = self.stages[stage_name]
        result = StageResult(
            name=stage_name,
            status=StageStatus.PENDING,
            start_time=datetime.utcnow()
        )

        # Check dependencies
        for dep in stage.depends_on:
            if dep in self.results and not self.results[dep].success:
                if not stage.optional:
                    result.status = StageStatus.FAILED
                    result.error = Exception(f"Dependency {dep} failed")
                    result.end_time = datetime.utcnow()
                    self.results[stage_name] = result
                    logger.error(f"Stage {stage_name} failed due to dependency {dep}")
                    return result
                else:
                    result.status = StageStatus.SKIPPED
                    result.end_time = datetime.utcnow()
                    self.results[stage_name] = result
                    logger.info(f"Optional stage {stage_name} skipped due to dependency {dep}")
                    return result

        # Execute stage
        logger.info(f"Executing stage: {stage_name}")
        result.status = StageStatus.RUNNING

        attempt = 0
        while attempt < (stage.max_retries if stage.retry_on_failure else 1):
            try:
                # Execute with timeout if specified
                if stage.timeout:
                    result.output = await asyncio.wait_for(
                        stage.function(*stage.args, **stage.kwargs),
                        timeout=stage.timeout
                    )
                else:
                    result.output = await stage.function(*stage.args, **stage.kwargs)

                result.status = StageStatus.COMPLETED
                break

            except asyncio.TimeoutError:
                result.error = TimeoutError(f"Stage {stage_name} timed out after {stage.timeout}s")
                result.status = StageStatus.FAILED
                logger.error(f"Stage {stage_name} timed out")
                break

            except Exception as e:
                result.error = e
                result.status = StageStatus.FAILED
                attempt += 1

                if attempt < stage.max_retries and stage.retry_on_failure:
                    logger.warning(
                        f"Stage {stage_name} failed (attempt {attempt}/{stage.max_retries}): {str(e)}"
                    )
                    await asyncio.sleep(1 * attempt)  # Exponential backoff
                else:
                    logger.error(f"Stage {stage_name} failed: {str(e)}")
                    break

        result.end_time = datetime.utcnow()
        result.duration_seconds = (
            result.end_time - result.start_time
        ).total_seconds()

        self.results[stage_name] = result

        # Log result
        if result.success:
            logger.info(f"Stage {stage_name} completed in {result.duration_seconds:.2f}s")
        else:
            logger.error(f"Stage {stage_name} failed: {result.error}")

        return result

    async def _execute_parallel(self,
                              stage_names: List[str],
                              skip_stages: List[str]):
        """
        Execute multiple stages in parallel.

        Args:
            stage_names: List of stage names to execute
            skip_stages: List of stages to skip
        """
        logger.info(f"Executing stages in parallel: {stage_names}")

        tasks = [
            self._execute_stage(name, skip_stages)
            for name in stage_names
        ]

        await asyncio.gather(*tasks, return_exceptions=True)

    def get_successful_stages(self) -> List[str]:
        """Get list of successfully completed stages"""
        return [
            name for name, result in self.results.items()
            if result.success
        ]

    def get_failed_stages(self) -> List[str]:
        """Get list of failed stages"""
        return [
            name for name, result in self.results.items()
            if result.status == StageStatus.FAILED
        ]

    def get_stage_output(self, stage_name: str) -> Optional[Any]:
        """
        Get output from a specific stage.

        Args:
            stage_name: Name of the stage

        Returns:
            Stage output or None
        """
        if stage_name in self.results:
            return self.results[stage_name].output
        return None

    def clear_results(self):
        """Clear all execution results"""
        self.results = {}