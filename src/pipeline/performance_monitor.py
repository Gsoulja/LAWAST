"""
Performance monitoring for pipeline execution
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import statistics

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Performance metrics for a request or stage"""
    duration: float
    success: bool
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageMetrics:
    """Metrics for a specific pipeline stage"""
    name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    durations: List[float] = field(default_factory=list)

    @property
    def average_duration(self) -> float:
        """Calculate average duration"""
        if self.total_requests == 0:
            return 0.0
        return self.total_duration / self.total_requests

    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 0.0
        return self.successful_requests / self.total_requests

    @property
    def p50(self) -> float:
        """Calculate 50th percentile (median)"""
        if not self.durations:
            return 0.0
        return statistics.median(self.durations)

    @property
    def p95(self) -> float:
        """Calculate 95th percentile"""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.95)
        return sorted_durations[min(index, len(sorted_durations) - 1)]

    @property
    def p99(self) -> float:
        """Calculate 99th percentile"""
        if not self.durations:
            return 0.0
        sorted_durations = sorted(self.durations)
        index = int(len(sorted_durations) * 0.99)
        return sorted_durations[min(index, len(sorted_durations) - 1)]


class PerformanceMonitor:
    """
    Monitors performance metrics for pipeline execution.
    Tracks latency, success rates, and other metrics per stage.
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor.

        Args:
            max_history: Maximum number of metrics to keep in history
        """
        self.max_history = max_history
        self.stage_metrics: Dict[str, StageMetrics] = {}
        self.request_metrics: Dict[str, Dict[str, Any]] = {}
        self.active_requests: Dict[str, Dict[str, Any]] = {}
        self.global_metrics = StageMetrics(name="global")

    def start_request(self, trace_id: str):
        """
        Start monitoring a request.

        Args:
            trace_id: Unique trace ID for the request
        """
        self.active_requests[trace_id] = {
            "start_time": time.time(),
            "stages": {}
        }
        logger.debug(f"Started monitoring request: {trace_id}")

    def end_request(self, trace_id: str, duration: float):
        """
        End monitoring a request.

        Args:
            trace_id: Unique trace ID for the request
            duration: Total duration of the request
        """
        if trace_id in self.active_requests:
            request_data = self.active_requests.pop(trace_id)
            self.request_metrics[trace_id] = {
                "duration": duration,
                "stages": request_data.get("stages", {}),
                "timestamp": datetime.utcnow()
            }

            # Update global metrics
            self._update_metrics(self.global_metrics, duration, True)

            # Limit history
            if len(self.request_metrics) > self.max_history:
                oldest_keys = list(self.request_metrics.keys())[:len(self.request_metrics) - self.max_history]
                for key in oldest_keys:
                    del self.request_metrics[key]

            logger.debug(f"Ended monitoring request: {trace_id} (duration: {duration:.2f}s)")

    def start_stage(self, trace_id: str, stage_name: str):
        """
        Start monitoring a stage within a request.

        Args:
            trace_id: Unique trace ID for the request
            stage_name: Name of the stage
        """
        if trace_id in self.active_requests:
            self.active_requests[trace_id]["stages"][stage_name] = {
                "start_time": time.time()
            }
            logger.debug(f"Started monitoring stage '{stage_name}' for request: {trace_id}")

    def end_stage(self, trace_id: str, stage_name: str, success: bool = True):
        """
        End monitoring a stage within a request.

        Args:
            trace_id: Unique trace ID for the request
            stage_name: Name of the stage
            success: Whether the stage was successful
        """
        if trace_id in self.active_requests and stage_name in self.active_requests[trace_id]["stages"]:
            stage_data = self.active_requests[trace_id]["stages"][stage_name]
            duration = time.time() - stage_data["start_time"]
            stage_data["duration"] = duration
            stage_data["success"] = success

            # Update stage metrics
            if stage_name not in self.stage_metrics:
                self.stage_metrics[stage_name] = StageMetrics(name=stage_name)

            self._update_metrics(self.stage_metrics[stage_name], duration, success)

            logger.debug(
                f"Ended monitoring stage '{stage_name}' for request: {trace_id} "
                f"(duration: {duration:.2f}s, success: {success})"
            )

    def _update_metrics(self, metrics: StageMetrics, duration: float, success: bool):
        """
        Update metrics with a new measurement.

        Args:
            metrics: Metrics object to update
            duration: Duration of the operation
            success: Whether the operation was successful
        """
        metrics.total_requests += 1
        metrics.total_duration += duration
        metrics.durations.append(duration)

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1

        metrics.min_duration = min(metrics.min_duration, duration)
        metrics.max_duration = max(metrics.max_duration, duration)

        # Limit duration history
        if len(metrics.durations) > self.max_history:
            metrics.durations = metrics.durations[-self.max_history:]

    def get_stage_metrics(self, stage_name: str) -> Optional[StageMetrics]:
        """
        Get metrics for a specific stage.

        Args:
            stage_name: Name of the stage

        Returns:
            Stage metrics or None
        """
        return self.stage_metrics.get(stage_name)

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all performance metrics.

        Returns:
            Dictionary containing all metrics
        """
        return {
            "global": self._metrics_to_dict(self.global_metrics),
            "stages": {
                name: self._metrics_to_dict(metrics)
                for name, metrics in self.stage_metrics.items()
            },
            "recent_requests": self._get_recent_requests(10)
        }

    def _metrics_to_dict(self, metrics: StageMetrics) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_requests": metrics.total_requests,
            "successful_requests": metrics.successful_requests,
            "failed_requests": metrics.failed_requests,
            "success_rate": f"{metrics.success_rate * 100:.1f}%",
            "average_duration": f"{metrics.average_duration:.3f}s",
            "min_duration": f"{metrics.min_duration:.3f}s" if metrics.min_duration != float('inf') else "N/A",
            "max_duration": f"{metrics.max_duration:.3f}s",
            "p50": f"{metrics.p50:.3f}s",
            "p95": f"{metrics.p95:.3f}s",
            "p99": f"{metrics.p99:.3f}s"
        }

    def _get_recent_requests(self, count: int) -> List[Dict[str, Any]]:
        """Get recent request metrics"""
        recent = []
        sorted_requests = sorted(
            self.request_metrics.items(),
            key=lambda x: x[1]["timestamp"],
            reverse=True
        )

        for trace_id, data in sorted_requests[:count]:
            recent.append({
                "trace_id": trace_id,
                "duration": f"{data['duration']:.3f}s",
                "timestamp": data["timestamp"].isoformat(),
                "stages": {
                    name: f"{stage['duration']:.3f}s"
                    for name, stage in data.get("stages", {}).items()
                }
            })

        return recent

    def get_performance_report(self) -> str:
        """
        Generate a human-readable performance report.

        Returns:
            Performance report as string
        """
        metrics = self.get_all_metrics()

        report = "Pipeline Performance Report\n"
        report += "=" * 50 + "\n\n"

        # Global metrics
        global_metrics = metrics["global"]
        report += "Overall Performance:\n"
        report += f"  Total Requests: {global_metrics['total_requests']}\n"
        report += f"  Success Rate: {global_metrics['success_rate']}\n"
        report += f"  Average Duration: {global_metrics['average_duration']}\n"
        report += f"  P50 Latency: {global_metrics['p50']}\n"
        report += f"  P95 Latency: {global_metrics['p95']}\n"
        report += f"  P99 Latency: {global_metrics['p99']}\n\n"

        # Stage metrics
        if metrics["stages"]:
            report += "Stage Performance:\n"
            for stage_name, stage_metrics in metrics["stages"].items():
                report += f"\n  {stage_name}:\n"
                report += f"    Requests: {stage_metrics['total_requests']}\n"
                report += f"    Success Rate: {stage_metrics['success_rate']}\n"
                report += f"    Avg Duration: {stage_metrics['average_duration']}\n"
                report += f"    P95 Latency: {stage_metrics['p95']}\n"

        # Recent requests
        if metrics["recent_requests"]:
            report += "\nRecent Requests:\n"
            for req in metrics["recent_requests"][:5]:
                report += f"  {req['trace_id'][:8]}... - {req['duration']} - {req['timestamp']}\n"

        return report

    def reset_metrics(self):
        """Reset all metrics"""
        self.stage_metrics = {}
        self.request_metrics = {}
        self.active_requests = {}
        self.global_metrics = StageMetrics(name="global")
        logger.info("Performance metrics reset")

    def export_metrics_prometheus(self) -> str:
        """
        Export metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format
        """
        output = []

        # Global metrics
        output.append(f"# HELP pipeline_requests_total Total number of pipeline requests")
        output.append(f"# TYPE pipeline_requests_total counter")
        output.append(f"pipeline_requests_total {self.global_metrics.total_requests}")

        output.append(f"# HELP pipeline_success_rate Pipeline success rate")
        output.append(f"# TYPE pipeline_success_rate gauge")
        output.append(f"pipeline_success_rate {self.global_metrics.success_rate}")

        output.append(f"# HELP pipeline_duration_seconds Pipeline request duration")
        output.append(f"# TYPE pipeline_duration_seconds summary")
        output.append(f"pipeline_duration_seconds{{quantile=\"0.5\"}} {self.global_metrics.p50}")
        output.append(f"pipeline_duration_seconds{{quantile=\"0.95\"}} {self.global_metrics.p95}")
        output.append(f"pipeline_duration_seconds{{quantile=\"0.99\"}} {self.global_metrics.p99}")
        output.append(f"pipeline_duration_seconds_sum {self.global_metrics.total_duration}")
        output.append(f"pipeline_duration_seconds_count {self.global_metrics.total_requests}")

        # Stage metrics
        for stage_name, metrics in self.stage_metrics.items():
            safe_name = stage_name.replace("-", "_").replace(" ", "_")

            output.append(f"# HELP pipeline_stage_requests_total Total requests for stage {stage_name}")
            output.append(f"# TYPE pipeline_stage_requests_total counter")
            output.append(f"pipeline_stage_requests_total{{stage=\"{stage_name}\"}} {metrics.total_requests}")

            output.append(f"# HELP pipeline_stage_duration_seconds Duration for stage {stage_name}")
            output.append(f"# TYPE pipeline_stage_duration_seconds summary")
            output.append(f"pipeline_stage_duration_seconds{{stage=\"{stage_name}\",quantile=\"0.5\"}} {metrics.p50}")
            output.append(f"pipeline_stage_duration_seconds{{stage=\"{stage_name}\",quantile=\"0.95\"}} {metrics.p95}")
            output.append(f"pipeline_stage_duration_seconds{{stage=\"{stage_name}\",quantile=\"0.99\"}} {metrics.p99}")

        return "\n".join(output)