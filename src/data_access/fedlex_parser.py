"""
Fedlex JSON parser with streaming and batch processing support
"""
import json
import ijson
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, Generator
from datetime import datetime

from .batch_processor import BatchProcessor
from .graph_builder import GraphBuilder
from ..extractors import LawExtractor, VersionExtractor, ActExtractor, ExtractionResult

logger = logging.getLogger(__name__)


class FedlexParser:
    """
    Main parser for Fedlex JSON files with streaming and batch processing
    
    Features:
    - Streaming JSON parsing for large files
    - Batch processing with checkpointing
    - Support for all JSON types (ConsolidationAbstract, Consolidation, Act)
    - Error recovery and progress tracking
    - Memory-efficient processing
    """

    def __init__(
        self,
        batch_size: Optional[int] = None,
        checkpoint_file: Optional[str] = None,
        max_workers: Optional[int] = None
    ):
        """
        Initialize the Fedlex parser
        
        Args:
            batch_size: Number of files to process per batch
            checkpoint_file: Path to checkpoint file for recovery
            max_workers: Number of parallel workers
        """
        self.batch_size = batch_size or int(os.getenv('BATCH_SIZE', 1000))
        self.checkpoint_file = checkpoint_file or os.getenv('CHECKPOINT_FILE', 'fedlex_processing_checkpoint.json')
        self.max_workers = max_workers or int(os.getenv('MAX_WORKERS', 4))
        
        # Initialize components
        self.batch_processor = BatchProcessor(
            batch_size=self.batch_size,
            checkpoint_file=self.checkpoint_file,
            max_workers=self.max_workers
        )
        self.graph_builder = GraphBuilder()
        
        # Initialize extractors
        self.extractors = {
            'law': LawExtractor(),
            'version': VersionExtractor(),
            'act': ActExtractor()
        }
        
        # Statistics
        self.total_nodes_created = 0
        self.total_relationships_created = 0
        self.processing_start_time = None

    def parse_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Parse a single JSON file with streaming
        
        Args:
            file_path: Path to the JSON file
            
        Returns:
            Dictionary with parsing results and statistics
        """
        result = {
            'file_path': str(file_path),
            'success': False,
            'nodes_created': 0,
            'relationships_created': 0,
            'extraction_results': [],
            'errors': []
        }
        
        try:
            # Parse JSON with streaming for large files
            json_data = self._stream_json_file(file_path)
            
            if not json_data:
                result['errors'].append(f"Failed to parse JSON from {file_path}")
                return result
            
            # Determine file type and extract entities
            extraction_results = self._extract_entities(json_data, str(file_path))
            
            # Process extraction results
            for extraction_result in extraction_results:
                if extraction_result.nodes:
                    # Create nodes in Neo4j
                    nodes_created = self._create_nodes(extraction_result.nodes)
                    result['nodes_created'] += nodes_created
                
                if extraction_result.relationships:
                    # Create relationships in Neo4j
                    relationships_created = self._create_relationships(extraction_result.relationships)
                    result['relationships_created'] += relationships_created
                
                # Collect errors
                result['errors'].extend(extraction_result.errors)
                
                # Store extraction result for debugging
                result['extraction_results'].append({
                    'extractor': extraction_result.__class__.__name__ if hasattr(extraction_result, '__class__') else 'Unknown',
                    'nodes': len(extraction_result.nodes),
                    'relationships': len(extraction_result.relationships),
                    'statistics': extraction_result.statistics
                })
            
            result['success'] = True
            logger.debug(f"Successfully processed {file_path}: {result['nodes_created']} nodes, {result['relationships_created']} relationships")
            
        except Exception as e:
            error_msg = f"Failed to process {file_path}: {str(e)}"
            result['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return result

    def process_directory(
        self,
        directory: Path,
        limit: Optional[int] = None,
        resume: bool = True
    ) -> Dict[str, Any]:
        """
        Process an entire directory of JSON files
        
        Args:
            directory: Directory containing JSON files
            limit: Maximum number of files to process
            resume: Whether to resume from checkpoint
            
        Returns:
            Processing summary with statistics
        """
        self.processing_start_time = datetime.now()
        
        logger.info(f"Starting Fedlex JSON processing: {directory}")
        logger.info(f"Configuration: batch_size={self.batch_size}, limit={limit}, resume={resume}")
        
        # Find all JSON files
        json_files = self._find_json_files(directory)
        
        if limit:
            json_files = json_files[:limit]
        
        logger.info(f"Found {len(json_files)} JSON files to process")
        
        # Process files with batch processor
        def processor_func(file_path: Path) -> Dict[str, Any]:
            return self.parse_file(file_path)
        
        checkpoint = self.batch_processor.process_files(
            json_files,
            processor_func,
            resume=resume,
            save_interval=100
        )
        
        # Calculate final statistics
        processing_time = (datetime.now() - self.processing_start_time).total_seconds()
        
        summary = {
            'directory': str(directory),
            'files_processed': checkpoint.processed_files,
            'files_failed': checkpoint.failed_files,
            'total_files': checkpoint.total_files,
            'processing_time_seconds': processing_time,
            'files_per_second': checkpoint.processed_files / processing_time if processing_time > 0 else 0,
            'statistics': checkpoint.statistics,
            'errors': checkpoint.errors,
            'success_rate': (checkpoint.processed_files / checkpoint.total_files * 100) if checkpoint.total_files > 0 else 0
        }
        
        logger.info(f"Processing complete: {summary}")
        return summary

    def _stream_json_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Stream parse JSON file without loading entirely into memory
        
        Args:
            file_path: Path to JSON file
            
        Returns:
            Parsed JSON data or None if parsing fails
        """
        try:
            file_size = file_path.stat().st_size
            
            # For small files (< 1MB), use standard JSON parsing
            if file_size < 1024 * 1024:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            # For large files, use ijson streaming
            logger.debug(f"Using streaming parser for large file: {file_path} ({file_size} bytes)")
            
            with open(file_path, 'rb') as f:
                # Parse the entire JSON structure
                parser = ijson.parse(f)
                
                # Build the JSON structure incrementally
                json_data = {}
                stack = [json_data]
                keys = ['']
                
                for prefix, event, value in parser:
                    if event == 'start_map':
                        if prefix:
                            new_dict = {}
                            self._set_nested_value(json_data, prefix, new_dict)
                            stack.append(new_dict)
                            keys.append(prefix)
                    elif event == 'end_map':
                        if len(stack) > 1:
                            stack.pop()
                            keys.pop()
                    elif event == 'start_array':
                        if prefix:
                            new_list = []
                            self._set_nested_value(json_data, prefix, new_list)
                    elif event in ('string', 'number', 'boolean', 'null'):
                        if prefix:
                            self._set_nested_value(json_data, prefix, value)
                
                return json_data
                
        except Exception as e:
            logger.error(f"Failed to parse JSON file {file_path}: {e}")
            return None

    def _set_nested_value(self, data: Dict, path: str, value: Any):
        """Set a nested value in a dictionary using dot notation"""
        keys = path.split('.')
        current = data
        
        for key in keys[:-1]:
            if key.isdigit():
                # Array index
                key = int(key)
                while len(current) <= key:
                    current.append({})
                if not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
            else:
                # Dictionary key
                if key not in current:
                    current[key] = {}
                current = current[key]
        
        final_key = keys[-1]
        if final_key.isdigit():
            final_key = int(final_key)
            while len(current) <= final_key:
                current.append(None)
            current[final_key] = value
        else:
            current[final_key] = value

    def _extract_entities(self, json_data: Dict[str, Any], file_path: str) -> List[ExtractionResult]:
        """
        Extract entities from JSON data using appropriate extractors
        
        Args:
            json_data: Parsed JSON data
            file_path: File path for context
            
        Returns:
            List of extraction results
        """
        results = []
        
        # Determine which extractors to use based on content
        data_section = json_data.get('data', {})
        types = data_section.get('type', [])
        
        if not isinstance(types, list):
            types = [types] if types else []
        
        uri = data_section.get('uri', '')
        
        # Try Law extractor for ConsolidationAbstract
        if 'ConsolidationAbstract' in types:
            result = self.extractors['law'].extract(json_data, file_path)
            if result.nodes or result.errors:
                results.append(result)
        
        # Try Version extractor for Consolidation or version files
        if ('Consolidation' in types or 
            'Expression' in types or 
            self._is_version_file(uri, file_path)):
            result = self.extractors['version'].extract(json_data, file_path)
            if result.nodes or result.errors:
                results.append(result)
        
        # Try Act extractor for Acts or publication files
        if ('Act' in types or 
            '/eli/oc/' in file_path or 
            '/eli/fga/' in file_path):
            result = self.extractors['act'].extract(json_data, file_path)
            if result.nodes or result.errors:
                results.append(result)
        
        # If no specific extractor matched, log for investigation
        if not results:
            logger.debug(f"No extractors matched for file {file_path} with types: {types}")
        
        return results

    def _is_version_file(self, uri: str, file_path: str) -> bool:
        """Check if this appears to be a version file"""
        # Version files typically have date patterns in URI or filename
        return (len(uri.split('/')) > 5 and 
                any(part.isdigit() and len(part) == 8 for part in uri.split('/')))

    def _create_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """
        Create nodes in Neo4j using GraphBuilder
        
        Args:
            nodes: List of node dictionaries
            
        Returns:
            Number of nodes created
        """
        if not nodes:
            return 0
        
        try:
            # Group nodes by type for efficient batch creation
            nodes_by_type = {}
            for node in nodes:
                node_type = node.get('type', 'Unknown')
                if node_type not in nodes_by_type:
                    nodes_by_type[node_type] = []
                nodes_by_type[node_type].append(node)
            
            total_created = 0
            
            for node_type, typed_nodes in nodes_by_type.items():
                # Convert to appropriate node objects
                if node_type == 'Law':
                    created = self._batch_create_law_nodes(typed_nodes)
                elif node_type == 'Version':
                    created = self._batch_create_version_nodes(typed_nodes)
                elif node_type == 'Act':
                    created = self._batch_create_act_nodes(typed_nodes)
                elif node_type in ['Expression', 'Manifestation']:
                    created = self._batch_create_generic_nodes(typed_nodes, node_type)
                else:
                    logger.warning(f"Unknown node type: {node_type}")
                    created = 0
                
                total_created += created
            
            return total_created
            
        except Exception as e:
            logger.error(f"Failed to create nodes: {e}")
            return 0

    def _batch_create_law_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """Create Law nodes in batch"""
        # Use raw Cypher for efficiency
        query = """
        UNWIND $nodes AS node
        MERGE (l:Law {uri: node.uri})
        SET l += node
        RETURN count(l) as created
        """
        try:
            result = self.graph_builder.connection.execute_write(query, {"nodes": nodes})
            return result[0]['created'] if result else 0
        except Exception as e:
            logger.error(f"Failed to create Law nodes: {e}")
            return 0

    def _batch_create_version_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """Create Version nodes in batch"""
        query = """
        UNWIND $nodes AS node
        MERGE (v:Version {uri: node.uri})
        SET v += node
        RETURN count(v) as created
        """
        try:
            result = self.graph_builder.connection.execute_write(query, {"nodes": nodes})
            return result[0]['created'] if result else 0
        except Exception as e:
            logger.error(f"Failed to create Version nodes: {e}")
            return 0

    def _batch_create_act_nodes(self, nodes: List[Dict[str, Any]]) -> int:
        """Create Act nodes in batch"""
        query = """
        UNWIND $nodes AS node
        MERGE (a:Act {uri: node.uri})
        SET a += node
        RETURN count(a) as created
        """
        try:
            result = self.graph_builder.connection.execute_write(query, {"nodes": nodes})
            return result[0]['created'] if result else 0
        except Exception as e:
            logger.error(f"Failed to create Act nodes: {e}")
            return 0

    def _batch_create_generic_nodes(self, nodes: List[Dict[str, Any]], node_type: str) -> int:
        """Create generic nodes (Expression, Manifestation) in batch"""
        query = f"""
        UNWIND $nodes AS node
        MERGE (n:{node_type} {{uri: node.uri}})
        SET n += node
        RETURN count(n) as created
        """
        try:
            result = self.graph_builder.connection.execute_write(query, {"nodes": nodes})
            return result[0]['created'] if result else 0
        except Exception as e:
            logger.error(f"Failed to create {node_type} nodes: {e}")
            return 0

    def _create_relationships(self, relationships: List[tuple]) -> int:
        """
        Create relationships in Neo4j
        
        Args:
            relationships: List of (from_uri, to_uri, rel_type, properties) tuples
            
        Returns:
            Number of relationships created
        """
        if not relationships:
            return 0
        
        try:
            return self.graph_builder.batch_create_relationships(relationships, batch_size=self.batch_size)
        except Exception as e:
            logger.error(f"Failed to create relationships: {e}")
            return 0

    def _find_json_files(self, directory: Path) -> List[Path]:
        """
        Find all JSON files in directory and subdirectories
        
        Args:
            directory: Root directory to search
            
        Returns:
            Sorted list of JSON file paths
        """
        json_files = []
        
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.json'):
                    json_files.append(Path(root) / file)
        
        # Sort files for consistent processing order
        json_files.sort()
        
        return json_files

    def get_statistics(self) -> Dict[str, Any]:
        """Get processing statistics"""
        return {
            'total_nodes_created': self.total_nodes_created,
            'total_relationships_created': self.total_relationships_created,
            'batch_processor_stats': self.batch_processor.checkpoint.statistics,
            'graph_stats': self.graph_builder.get_statistics()
        }
