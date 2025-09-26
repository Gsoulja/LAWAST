"""
Async wrapper utilities for synchronous components
"""

import asyncio
import functools
import logging
from typing import Any, Callable, TypeVar, Optional
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

T = TypeVar('T')


class AsyncWrapper:
    """
    Provides utilities to wrap synchronous functions for async execution.
    Uses thread pool executor to avoid blocking the event loop.
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize async wrapper.

        Args:
            max_workers: Maximum number of worker threads
        """
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        logger.info(f"AsyncWrapper initialized with {max_workers} workers")

    async def run_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Run a synchronous function asynchronously using thread pool.

        Args:
            func: Synchronous function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the synchronous function
        """
        loop = asyncio.get_event_loop()

        # Create partial function with arguments
        partial_func = functools.partial(func, *args, **kwargs)

        try:
            # Run in executor
            result = await loop.run_in_executor(
                self.executor,
                partial_func
            )
            return result
        except Exception as e:
            logger.error(f"Error executing {func.__name__}: {str(e)}")
            raise

    async def run_sync_with_timeout(self,
                                   func: Callable[..., T],
                                   timeout: float,
                                   *args,
                                   **kwargs) -> Optional[T]:
        """
        Run a synchronous function with timeout.

        Args:
            func: Synchronous function to execute
            timeout: Timeout in seconds
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result from the function or None if timeout
        """
        try:
            result = await asyncio.wait_for(
                self.run_sync(func, *args, **kwargs),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"{func.__name__} timed out after {timeout} seconds")
            return None
        except Exception as e:
            logger.error(f"Error executing {func.__name__}: {str(e)}")
            raise

    async def run_parallel(self,
                         functions: list[tuple[Callable, tuple, dict]]) -> list[Any]:
        """
        Run multiple synchronous functions in parallel.

        Args:
            functions: List of (function, args, kwargs) tuples

        Returns:
            List of results in the same order as input
        """
        tasks = []

        for func, args, kwargs in functions:
            task = self.run_sync(func, *args, **kwargs)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any exceptions
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                func_name = functions[i][0].__name__
                logger.error(f"Error in parallel execution of {func_name}: {str(result)}")

        return results

    def make_async(self, func: Callable[..., T]) -> Callable[..., asyncio.Future[T]]:
        """
        Decorator to make a synchronous function async.

        Args:
            func: Synchronous function to wrap

        Returns:
            Async version of the function
        """
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await self.run_sync(func, *args, **kwargs)

        return async_wrapper

    def __del__(self):
        """Cleanup executor on deletion"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False)


class AsyncContextManager:
    """
    Async context manager for synchronous resources.
    Useful for wrapping synchronous database connections, file handles, etc.
    """

    def __init__(self,
                sync_resource: Any,
                setup_method: Optional[str] = None,
                cleanup_method: Optional[str] = None):
        """
        Initialize async context manager.

        Args:
            sync_resource: The synchronous resource to manage
            setup_method: Optional method name to call on enter
            cleanup_method: Optional method name to call on exit
        """
        self.resource = sync_resource
        self.setup_method = setup_method
        self.cleanup_method = cleanup_method
        self.wrapper = AsyncWrapper()

    async def __aenter__(self):
        """Async enter"""
        if self.setup_method and hasattr(self.resource, self.setup_method):
            setup_func = getattr(self.resource, self.setup_method)
            await self.wrapper.run_sync(setup_func)
        return self.resource

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async exit"""
        if self.cleanup_method and hasattr(self.resource, self.cleanup_method):
            cleanup_func = getattr(self.resource, self.cleanup_method)
            await self.wrapper.run_sync(cleanup_func)
        return False


def async_retry(max_attempts: int = 3,
               delay: float = 1.0,
               backoff: float = 2.0,
               exceptions: tuple = (Exception,)):
    """
    Decorator for async retry logic.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier for delay
        exceptions: Tuple of exceptions to catch

    Returns:
        Decorated async function with retry logic
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}"
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}"
                        )

            raise last_exception

        return wrapper
    return decorator