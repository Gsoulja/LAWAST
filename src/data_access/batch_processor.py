"""
Batch processing utilities for large-scale data operations
"""
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Generator
from concurrent.futures import ThreadPoolExecutor, as_completed

from .graph_builder import GraphBuilder
from .neo4j_connection import get_connection

logger = logging.getLogger(__name__)


@dataclass
class ProcessingCheckpoint:
    """
    Represents a processing checkpoint for recovery
    """
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    last_processed_file: Optional[str] = None
    start_time: Optional[datetime] = None
    errors: List[Dict[str, Any]] = field(default_factory=list)
    statistics: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "total_files": self.total_files,
            "processed_files": self.processed_files,
            "failed_files": self.failed_files,
            "last_processed_file": self.last_processed_file,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "errors": self.errors,
            "statistics": self.statistics
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingCheckpoint":
        """Create from dictionary"""
        checkpoint = cls(
            total_files=data.get("total_files", 0),
            processed_files=data.get("processed_files", 0),
            failed_files=data.get("failed_files", 0),
            last_processed_file=data.get("last_processed_file"),
            errors=data.get("errors", []),
            statistics=data.get("statistics", {})
        )
        if data.get("start_time"):
            checkpoint.start_time = datetime.fromisoformat(data["start_time"])
        return checkpoint


class BatchProcessor:
    """
    Handles batch processing of files with checkpointing and error recovery
    """

    def __init__(
        self,
        graph_builder: Optional[GraphBuilder] = None,
        batch_size: int = 1000,
        checkpoint_file: str = "processing_checkpoint.json",
        max_workers: int = 4
    ):
        """
        Initialize the batch processor

        Args:
            graph_builder: GraphBuilder instance
            batch_size: Number of items to process per batch
            checkpoint_file: Path to checkpoint file
            max_workers: Number of parallel workers
        """
        self.graph_builder = graph_builder or GraphBuilder()
        self.batch_size = int(os.getenv("BATCH_SIZE", batch_size))
        self.checkpoint_file = checkpoint_file
        self.max_workers = max_workers
        self.checkpoint = ProcessingCheckpoint()

    def save_checkpoint(self):
        """Save the current checkpoint to file"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint.to_dict(), f, indent=2)
            logger.debug(f"Saved checkpoint: {self.checkpoint.processed_files}/{self.checkpoint.total_files}")
        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")

    def load_checkpoint(self) -> bool:
        """
        Load checkpoint from file if it exists

        Returns:
            True if checkpoint loaded, False otherwise
        """
        if not os.path.exists(self.checkpoint_file):
            return False

        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)
            self.checkpoint = ProcessingCheckpoint.from_dict(data)
            logger.info(f"Loaded checkpoint: {self.checkpoint.processed_files}/{self.checkpoint.total_files} processed")
            return True
        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return False

    def clear_checkpoint(self):
        """Clear the checkpoint file"""
        if os.path.exists(self.checkpoint_file):
            os.remove(self.checkpoint_file)
            logger.info("Cleared checkpoint file")
        self.checkpoint = ProcessingCheckpoint()

    def process_files(
        self,
        file_paths: List[Path],
        processor_func: Callable[[Path], Any],
        resume: bool = True,
        save_interval: int = 100
    ) -> ProcessingCheckpoint:
        """
        Process a list of files with checkpointing

        Args:
            file_paths: List of file paths to process
            processor_func: Function to process each file
            resume: Whether to resume from checkpoint
            save_interval: Save checkpoint every N files

        Returns:
            Final processing checkpoint
        """
        # Load checkpoint if resuming
        if resume and self.load_checkpoint():
            # Filter already processed files
            if self.checkpoint.last_processed_file:
                try:
                    last_index = next(
                        i for i, p in enumerate(file_paths)
                        if str(p) == self.checkpoint.last_processed_file
                    )
                    file_paths = file_paths[last_index + 1:]
                    logger.info(f"Resuming from file {last_index + 1}")
                except StopIteration:
                    logger.warning("Could not find last processed file in list")
        else:
            self.checkpoint = ProcessingCheckpoint(
                total_files=len(file_paths),
                start_time=datetime.now()
            )

        # Update total files if not resuming
        if not resume:
            self.checkpoint.total_files = len(file_paths)

        # Process files
        for i, file_path in enumerate(file_paths):
            try:
                # Process the file
                result = processor_func(file_path)

                # Update statistics
                if isinstance(result, dict) and "statistics" in result:
                    for key, value in result["statistics"].items():
                        self.checkpoint.statistics[key] = \
                            self.checkpoint.statistics.get(key, 0) + value

                self.checkpoint.processed_files += 1
                self.checkpoint.last_processed_file = str(file_path)

                # Save checkpoint periodically
                if (self.checkpoint.processed_files % save_interval) == 0:
                    self.save_checkpoint()
                    self._log_progress()

            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                self.checkpoint.failed_files += 1
                self.checkpoint.errors.append({
                    "file": str(file_path),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })

        # Final save
        self.save_checkpoint()
        self._log_progress()

        return self.checkpoint

    def process_in_batches(
        self,
        items: List[Any],
        batch_func: Callable[[List[Any]], int],
        item_name: str = "items"
    ) -> int:
        """
        Process items in batches

        Args:
            items: List of items to process
            batch_func: Function to process a batch of items
            item_name: Name of items for logging

        Returns:
            Total number of items processed
        """
        total_processed = 0
        total_batches = (len(items) + self.batch_size - 1) // self.batch_size

        logger.info(f"Processing {len(items)} {item_name} in {total_batches} batches")

        for batch_num in range(0, len(items), self.batch_size):
            batch = items[batch_num:batch_num + self.batch_size]
            batch_idx = batch_num // self.batch_size + 1

            try:
                processed = batch_func(batch)
                total_processed += processed

                logger.info(
                    f"Batch {batch_idx}/{total_batches}: "
                    f"Processed {processed} {item_name} "
                    f"(Total: {total_processed}/{len(items)})"
                )

                # Update checkpoint statistics
                self.checkpoint.statistics[f"{item_name}_processed"] = total_processed

            except Exception as e:
                logger.error(f"Failed to process batch {batch_idx}: {e}")
                self.checkpoint.failed_files += len(batch)

        return total_processed

    def parallel_process(
        self,
        items: List[Any],
        processor_func: Callable[[Any], Any],
        item_name: str = "items"
    ) -> List[Any]:
        """
        Process items in parallel using thread pool

        Args:
            items: List of items to process
            processor_func: Function to process each item
            item_name: Name of items for logging

        Returns:
            List of results
        """
        results = []
        total = len(items)

        logger.info(f"Processing {total} {item_name} with {self.max_workers} workers")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(processor_func, item): item
                for item in items
            }

            # Process completed tasks
            completed = 0
            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                    completed += 1

                    if completed % 100 == 0:
                        logger.info(f"Processed {completed}/{total} {item_name}")

                except Exception as e:
                    logger.error(f"Failed to process item: {e}")
                    self.checkpoint.failed_files += 1

        logger.info(f"Completed processing {len(results)}/{total} {item_name}")
        return results

    def stream_json_files(
        self,
        directory: Path,
        pattern: str = "*.json"
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream JSON files from a directory

        Args:
            directory: Directory to scan
            pattern: File pattern to match

        Yields:
            Parsed JSON data with file path
        """
        json_files = sorted(directory.glob(pattern))
        logger.info(f"Found {len(json_files)} JSON files in {directory}")

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['_file_path'] = str(json_file)
                    yield data
            except Exception as e:
                logger.error(f"Failed to read {json_file}: {e}")
                self.checkpoint.failed_files += 1

    def _log_progress(self):
        """Log current processing progress"""
        if self.checkpoint.total_files > 0:
            progress = (self.checkpoint.processed_files / self.checkpoint.total_files) * 100
            elapsed = (datetime.now() - self.checkpoint.start_time).total_seconds() \
                if self.checkpoint.start_time else 0

            if elapsed > 0:
                rate = self.checkpoint.processed_files / elapsed
                eta = (self.checkpoint.total_files - self.checkpoint.processed_files) / rate \
                    if rate > 0 else 0

                logger.info(
                    f"Progress: {self.checkpoint.processed_files}/{self.checkpoint.total_files} "
                    f"({progress:.1f}%) | "
                    f"Failed: {self.checkpoint.failed_files} | "
                    f"Rate: {rate:.1f} files/sec | "
                    f"ETA: {eta:.0f}s"
                )
            else:
                logger.info(
                    f"Progress: {self.checkpoint.processed_files}/{self.checkpoint.total_files} "
                    f"({progress:.1f}%) | Failed: {self.checkpoint.failed_files}"
                )

        # Log statistics
        if self.checkpoint.statistics:
            stats_str = " | ".join(
                f"{k}: {v}" for k, v in self.checkpoint.statistics.items()
            )
            logger.info(f"Statistics: {stats_str}")


class ProgressTracker:
    """
    Simple progress tracker for console output
    """

    def __init__(self, total: int, description: str = "Processing"):
        """
        Initialize progress tracker

        Args:
            total: Total number of items
            description: Description of the task
        """
        self.total = total
        self.description = description
        self.current = 0
        self.start_time = time.time()

    def update(self, increment: int = 1):
        """Update progress"""
        self.current += increment
        self._display()

    def _display(self):
        """Display progress bar"""
        if self.total == 0:
            return

        progress = self.current / self.total
        bar_length = 40
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)

        elapsed = time.time() - self.start_time
        if elapsed > 0 and progress > 0:
            eta = (elapsed / progress) - elapsed
            rate = self.current / elapsed
            print(
                f"\r{self.description}: |{bar}| "
                f"{self.current}/{self.total} "
                f"({progress*100:.1f}%) "
                f"[{elapsed:.0f}s<{eta:.0f}s, {rate:.1f} it/s]",
                end=""
            )
        else:
            print(
                f"\r{self.description}: |{bar}| "
                f"{self.current}/{self.total} ({progress*100:.1f}%)",
                end=""
            )

        if self.current >= self.total:
            print()  # New line when complete

    def finish(self):
        """Mark as finished"""
        self.current = self.total
        self._display()