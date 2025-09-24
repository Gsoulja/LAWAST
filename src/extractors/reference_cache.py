"""
Reference Cache System for HTML Cross-Reference Extraction

Provides file-based caching for extracted references to avoid reprocessing
unchanged HTML files and improve performance on large datasets.
"""
import json
import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

from .base_extractor import ExtractionResult

logger = logging.getLogger(__name__)


class ReferenceCache:
    """
    File-based cache for HTML reference extraction results
    
    Uses file content hashes to detect changes and avoid reprocessing
    unchanged files. Supports cache expiration and cleanup.
    """
    
    def __init__(
        self,
        cache_dir: str = "data/cache",
        cache_file: str = "html_reference_cache.json",
        max_age_days: int = 30,
        max_cache_size_mb: int = 100
    ):
        """
        Initialize reference cache
        
        Args:
            cache_dir: Directory for cache files
            cache_file: Cache file name
            max_age_days: Maximum age for cache entries
            max_cache_size_mb: Maximum cache size in MB
        """
        self.cache_dir = Path(cache_dir)
        self.cache_file = self.cache_dir / cache_file
        self.max_age = timedelta(days=max_age_days)
        self.max_size_bytes = max_cache_size_mb * 1024 * 1024
        
        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize logger first
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Load existing cache
        self.cache = self._load_cache()
        
        # Statistics
        self.stats = {
            'hits': 0,
            'misses': 0,
            'saves': 0,
            'expired': 0,
            'errors': 0
        }
    
    def get_cached(self, file_path: str) -> Optional[ExtractionResult]:
        """
        Get cached extraction result for a file
        
        Args:
            file_path: Path to HTML file
            
        Returns:
            Cached ExtractionResult or None if not found/expired
        """
        try:
            # Calculate file hash
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                self.stats['misses'] += 1
                return None
            
            # Check if cached
            cache_key = self._get_cache_key(file_path)
            if cache_key not in self.cache:
                self.stats['misses'] += 1
                return None
            
            cache_entry = self.cache[cache_key]
            
            # Check if hash matches (file unchanged)
            if cache_entry.get('file_hash') != file_hash:
                self.logger.debug(f"File hash mismatch for {file_path}, cache invalid")
                self._remove_cache_entry(cache_key)
                self.stats['misses'] += 1
                return None
            
            # Check if expired
            if self._is_expired(cache_entry):
                self.logger.debug(f"Cache entry expired for {file_path}")
                self._remove_cache_entry(cache_key)
                self.stats['expired'] += 1
                return None
            
            # Reconstruct ExtractionResult
            result = self._deserialize_result(cache_entry['result'])
            if result:
                self.stats['hits'] += 1
                self.logger.debug(f"Cache hit for {file_path}")
                return result
            else:
                self.stats['misses'] += 1
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting cached result for {file_path}: {e}")
            self.stats['errors'] += 1
            return None
    
    def store(self, file_path: str, result: ExtractionResult) -> bool:
        """
        Store extraction result in cache
        
        Args:
            file_path: Path to HTML file
            result: Extraction result to cache
            
        Returns:
            True if stored successfully
        """
        try:
            # Calculate file hash
            file_hash = self._get_file_hash(file_path)
            if not file_hash:
                return False
            
            # Create cache entry
            cache_key = self._get_cache_key(file_path)
            cache_entry = {
                'file_path': file_path,
                'file_hash': file_hash,
                'timestamp': datetime.now().isoformat(),
                'result': self._serialize_result(result)
            }
            
            # Store in cache
            self.cache[cache_key] = cache_entry
            
            # Clean up if needed
            self._cleanup_if_needed()
            
            # Save cache
            if self._save_cache():
                self.stats['saves'] += 1
                self.logger.debug(f"Cached result for {file_path}")
                return True
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error storing cache for {file_path}: {e}")
            self.stats['errors'] += 1
            return False
    
    def clear_cache(self) -> bool:
        """
        Clear all cache entries
        
        Returns:
            True if cleared successfully
        """
        try:
            self.cache.clear()
            self._save_cache()
            self.logger.info("Cache cleared")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}")
            return False
    
    def cleanup_expired(self) -> int:
        """
        Remove expired cache entries
        
        Returns:
            Number of entries removed
        """
        removed_count = 0
        
        try:
            expired_keys = []
            for key, entry in self.cache.items():
                if self._is_expired(entry):
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.cache[key]
                removed_count += 1
            
            if removed_count > 0:
                self._save_cache()
                self.logger.info(f"Removed {removed_count} expired cache entries")
            
        except Exception as e:
            self.logger.error(f"Error during cache cleanup: {e}")
        
        return removed_count
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        
        Returns:
            Dictionary with cache statistics
        """
        cache_size = self._get_cache_size()
        
        return {
            'entries': len(self.cache),
            'size_mb': cache_size / (1024 * 1024),
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'saves': self.stats['saves'],
            'expired': self.stats['expired'],
            'errors': self.stats['errors'],
            'hit_rate': self.stats['hits'] / max(1, self.stats['hits'] + self.stats['misses']),
            'cache_file': str(self.cache_file)
        }
    
    def _get_file_hash(self, file_path: str) -> Optional[str]:
        """
        Calculate hash of file content
        
        Args:
            file_path: Path to file
            
        Returns:
            SHA256 hash or None if error
        """
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            return hashlib.sha256(content).hexdigest()
        except Exception as e:
            self.logger.debug(f"Could not hash file {file_path}: {e}")
            return None
    
    def _get_cache_key(self, file_path: str) -> str:
        """
        Generate cache key for file path
        
        Args:
            file_path: Path to file
            
        Returns:
            Cache key string
        """
        # Use relative path as key for portability
        try:
            rel_path = os.path.relpath(file_path)
            return hashlib.md5(rel_path.encode()).hexdigest()
        except Exception:
            return hashlib.md5(file_path.encode()).hexdigest()
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """
        Check if cache entry is expired
        
        Args:
            cache_entry: Cache entry to check
            
        Returns:
            True if expired
        """
        try:
            timestamp = datetime.fromisoformat(cache_entry['timestamp'])
            return datetime.now() - timestamp > self.max_age
        except Exception:
            return True  # Treat as expired if we can't parse timestamp
    
    def _serialize_result(self, result: ExtractionResult) -> Dict[str, Any]:
        """
        Serialize ExtractionResult to dictionary
        
        Args:
            result: ExtractionResult to serialize
            
        Returns:
            Serialized dictionary
        """
        return {
            'nodes': result.nodes,
            'relationships': result.relationships,
            'statistics': result.statistics,
            'errors': result.errors
        }
    
    def _deserialize_result(self, data: Dict[str, Any]) -> Optional[ExtractionResult]:
        """
        Deserialize dictionary to ExtractionResult
        
        Args:
            data: Serialized data
            
        Returns:
            ExtractionResult or None if error
        """
        try:
            result = ExtractionResult()
            result.nodes = data.get('nodes', [])
            result.relationships = data.get('relationships', [])
            result.statistics = data.get('statistics', {})
            result.errors = data.get('errors', [])
            return result
        except Exception as e:
            self.logger.error(f"Error deserializing result: {e}")
            return None
    
    def _load_cache(self) -> Dict[str, Any]:
        """
        Load cache from file
        
        Returns:
            Cache dictionary
        """
        if not self.cache_file.exists():
            return {}
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            self.logger.info(f"Loaded cache with {len(cache_data)} entries from {self.cache_file}")
            return cache_data
            
        except Exception as e:
            self.logger.warning(f"Could not load cache from {self.cache_file}: {e}")
            return {}
    
    def _save_cache(self) -> bool:
        """
        Save cache to file
        
        Returns:
            True if saved successfully
        """
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Could not save cache to {self.cache_file}: {e}")
            return False
    
    def _get_cache_size(self) -> int:
        """
        Get current cache file size in bytes
        
        Returns:
            File size in bytes
        """
        try:
            return self.cache_file.stat().st_size
        except Exception:
            return 0
    
    def _cleanup_if_needed(self):
        """Clean up cache if it exceeds size limit"""
        cache_size = self._get_cache_size()
        
        if cache_size > self.max_size_bytes:
            self.logger.info(f"Cache size ({cache_size / 1024 / 1024:.1f}MB) exceeds limit, cleaning up")
            
            # Sort by timestamp, remove oldest entries
            sorted_entries = sorted(
                self.cache.items(),
                key=lambda x: x[1].get('timestamp', ''),
                reverse=True  # Newest first
            )
            
            # Keep only the newest entries that fit in size limit
            keep_count = len(sorted_entries) // 2  # Remove half
            entries_to_keep = dict(sorted_entries[:keep_count])
            
            self.cache = entries_to_keep
            self.logger.info(f"Cleaned up cache, kept {len(self.cache)} entries")
    
    def _remove_cache_entry(self, cache_key: str):
        """Remove a specific cache entry"""
        if cache_key in self.cache:
            del self.cache[cache_key]
