"""
Configuration management for relationship extractor
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractorConfig:
    """
    Configuration for relationship extraction process
    """
    # Batch processing settings
    batch_size: int = 5000
    buffer_size: int = 5000
    max_buffer_size: int = 10000  # Maximum buffer size before forced flush

    # Transaction settings
    transaction_timeout: int = 300  # seconds
    checkpoint_interval: int = 10000  # Create checkpoint every N relationships
    enable_transactions: bool = True

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0  # seconds

    # Validation settings
    validate_nodes: bool = True
    skip_missing_nodes: bool = False  # If True, skip relationships with missing nodes

    # Performance settings
    parallel_extraction: bool = False
    num_workers: int = 4

    # Logging settings
    verbose: bool = False
    log_failed_relationships: bool = True

    @classmethod
    def from_env(cls) -> "ExtractorConfig":
        """
        Create configuration from environment variables
        """
        config = cls()

        # Override from environment
        if batch_size := os.getenv("EXTRACTOR_BATCH_SIZE"):
            config.batch_size = int(batch_size)

        if buffer_size := os.getenv("EXTRACTOR_BUFFER_SIZE"):
            config.buffer_size = int(buffer_size)

        if max_buffer := os.getenv("EXTRACTOR_MAX_BUFFER_SIZE"):
            config.max_buffer_size = int(max_buffer)

        if timeout := os.getenv("EXTRACTOR_TRANSACTION_TIMEOUT"):
            config.transaction_timeout = int(timeout)

        if checkpoint := os.getenv("EXTRACTOR_CHECKPOINT_INTERVAL"):
            config.checkpoint_interval = int(checkpoint)

        if validate := os.getenv("EXTRACTOR_VALIDATE_NODES"):
            config.validate_nodes = validate.lower() in ("true", "1", "yes")

        if skip_missing := os.getenv("EXTRACTOR_SKIP_MISSING_NODES"):
            config.skip_missing_nodes = skip_missing.lower() in ("true", "1", "yes")

        if max_retries := os.getenv("EXTRACTOR_MAX_RETRIES"):
            config.max_retries = int(max_retries)

        if verbose := os.getenv("EXTRACTOR_VERBOSE"):
            config.verbose = verbose.lower() in ("true", "1", "yes")

        return config

    def to_dict(self) -> dict:
        """Convert configuration to dictionary"""
        return {
            "batch_size": self.batch_size,
            "buffer_size": self.buffer_size,
            "max_buffer_size": self.max_buffer_size,
            "transaction_timeout": self.transaction_timeout,
            "checkpoint_interval": self.checkpoint_interval,
            "enable_transactions": self.enable_transactions,
            "max_retries": self.max_retries,
            "retry_delay": self.retry_delay,
            "validate_nodes": self.validate_nodes,
            "skip_missing_nodes": self.skip_missing_nodes,
            "parallel_extraction": self.parallel_extraction,
            "num_workers": self.num_workers,
            "verbose": self.verbose,
            "log_failed_relationships": self.log_failed_relationships
        }


# Default configuration instance
default_config = ExtractorConfig()