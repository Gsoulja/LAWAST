"""
Context Tree - Builds and manages conversation context trees
"""

import json
import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the context tree"""
    ROOT = "root"
    QUESTION = "question"
    ANSWER = "answer"
    CLARIFICATION = "clarification"
    EXTRACTED_INFO = "extracted_info"
    CONTEXT = "context"


@dataclass
class ContextNode:
    """A node in the context tree"""
    node_id: str
    node_type: NodeType
    content: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List['ContextNode'] = field(default_factory=list)
    parent_id: Optional[str] = None
    relevance_score: float = 1.0


@dataclass
class ExtractedInformation:
    """Information extracted from a conversation turn"""
    entities: Dict[str, List[str]]
    intent: str
    topics: List[str]
    constraints: List[str]
    preferences: Dict[str, Any]


class ContextTree:
    """Manages conversation context as a tree structure"""

    def __init__(self, max_depth: int = 10, pruning_threshold: float = 0.3):
        """
        Initialize the context tree.

        Args:
            max_depth: Maximum depth before pruning
            pruning_threshold: Relevance threshold for pruning
        """
        self.max_depth = max_depth
        self.pruning_threshold = pruning_threshold
        self.root = ContextNode(
            node_id="root",
            node_type=NodeType.ROOT,
            content="Conversation Start",
            timestamp=datetime.now().isoformat()
        )
        self.current_node = self.root
        self.node_index = {"root": self.root}
        self.turn_count = 0
        self.extracted_info = ExtractedInformation(
            entities={},
            intent="",
            topics=[],
            constraints=[],
            preferences={}
        )

    def add_question(self, question: str, metadata: Optional[Dict] = None) -> ContextNode:
        """
        Add a user question to the tree.

        Args:
            question: The user's question
            metadata: Optional metadata about the question

        Returns:
            The created question node
        """
        node_id = f"q_{self.turn_count}"
        node = ContextNode(
            node_id=node_id,
            node_type=NodeType.QUESTION,
            content=question,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
            parent_id=self.current_node.node_id
        )

        self.current_node.children.append(node)
        self.node_index[node_id] = node
        self.current_node = node
        self.turn_count += 1

        logger.debug(f"Added question node: {node_id}")
        return node

    def add_answer(self, answer: str, metadata: Optional[Dict] = None) -> ContextNode:
        """
        Add an agent answer to the tree.

        Args:
            answer: The agent's answer
            metadata: Optional metadata about the answer

        Returns:
            The created answer node
        """
        node_id = f"a_{self.turn_count}"
        node = ContextNode(
            node_id=node_id,
            node_type=NodeType.ANSWER,
            content=answer,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
            parent_id=self.current_node.node_id
        )

        self.current_node.children.append(node)
        self.node_index[node_id] = node

        logger.debug(f"Added answer node: {node_id}")
        return node

    def add_clarification(self,
                         clarification: str,
                         response: str,
                         metadata: Optional[Dict] = None) -> tuple[ContextNode, ContextNode]:
        """
        Add a clarification exchange to the tree.

        Args:
            clarification: The clarification question
            response: The user's response
            metadata: Optional metadata

        Returns:
            Tuple of (clarification node, response node)
        """
        # Add clarification question
        clarif_id = f"c_{self.turn_count}"
        clarif_node = ContextNode(
            node_id=clarif_id,
            node_type=NodeType.CLARIFICATION,
            content=clarification,
            timestamp=datetime.now().isoformat(),
            metadata=metadata or {},
            parent_id=self.current_node.node_id
        )

        self.current_node.children.append(clarif_node)
        self.node_index[clarif_id] = clarif_node

        # Add user response
        response_id = f"r_{self.turn_count}"
        response_node = ContextNode(
            node_id=response_id,
            node_type=NodeType.ANSWER,
            content=response,
            timestamp=datetime.now().isoformat(),
            parent_id=clarif_id
        )

        clarif_node.children.append(response_node)
        self.node_index[response_id] = response_node
        self.turn_count += 1

        logger.debug(f"Added clarification exchange: {clarif_id} -> {response_id}")
        return clarif_node, response_node

    def extract_and_store_info(self,
                               entities: Dict[str, List[str]],
                               intent: str = None,
                               topics: List[str] = None,
                               constraints: List[str] = None) -> ContextNode:
        """
        Extract and store information from the current conversation.

        Args:
            entities: Extracted entities
            intent: Identified intent
            topics: Identified topics
            constraints: Identified constraints

        Returns:
            The created extracted info node
        """
        # Update accumulated information
        for entity_type, values in entities.items():
            if entity_type not in self.extracted_info.entities:
                self.extracted_info.entities[entity_type] = []
            self.extracted_info.entities[entity_type].extend(values)

        if intent:
            self.extracted_info.intent = intent

        if topics:
            self.extracted_info.topics.extend(topics)
            # Remove duplicates while preserving order
            seen = set()
            self.extracted_info.topics = [
                t for t in self.extracted_info.topics
                if not (t in seen or seen.add(t))
            ]

        if constraints:
            self.extracted_info.constraints.extend(constraints)

        # Create extracted info node
        info_id = f"info_{self.turn_count}"
        info_node = ContextNode(
            node_id=info_id,
            node_type=NodeType.EXTRACTED_INFO,
            content=json.dumps({
                "entities": entities,
                "intent": intent,
                "topics": topics,
                "constraints": constraints
            }),
            timestamp=datetime.now().isoformat(),
            parent_id=self.current_node.node_id
        )

        self.current_node.children.append(info_node)
        self.node_index[info_id] = info_node

        logger.debug(f"Extracted and stored info: {info_id}")
        return info_node

    def get_context_path(self) -> List[ContextNode]:
        """
        Get the path from root to current node.

        Returns:
            List of nodes in the current context path
        """
        path = []
        node = self.current_node

        while node is not None:
            path.append(node)
            if node.parent_id:
                node = self.node_index.get(node.parent_id)
            else:
                break

        return list(reversed(path))

    def get_relevant_context(self, threshold: float = 0.5) -> List[ContextNode]:
        """
        Get relevant context nodes based on relevance scores.

        Args:
            threshold: Minimum relevance score

        Returns:
            List of relevant nodes
        """
        relevant = []

        def traverse(node: ContextNode):
            if node.relevance_score >= threshold:
                relevant.append(node)
            for child in node.children:
                traverse(child)

        traverse(self.root)
        return relevant

    def prune_tree(self) -> int:
        """
        Prune irrelevant branches from the tree.

        Returns:
            Number of nodes pruned
        """
        initial_count = len(self.node_index)

        def should_prune(node: ContextNode) -> bool:
            # Don't prune root or current path
            if node.node_type == NodeType.ROOT:
                return False
            if node in self.get_context_path():
                return False
            # Prune if relevance is below threshold
            return node.relevance_score < self.pruning_threshold

        def prune_recursive(node: ContextNode) -> List[ContextNode]:
            kept_children = []
            for child in node.children:
                if not should_prune(child):
                    prune_recursive(child)
                    kept_children.append(child)
                else:
                    # Remove from index
                    if child.node_id in self.node_index:
                        del self.node_index[child.node_id]
            node.children = kept_children
            return kept_children

        prune_recursive(self.root)
        pruned_count = initial_count - len(self.node_index)

        if pruned_count > 0:
            logger.info(f"Pruned {pruned_count} nodes from context tree")

        return pruned_count

    def update_relevance_scores(self, current_topics: List[str]) -> None:
        """
        Update relevance scores based on current topics.

        Args:
            current_topics: Current conversation topics
        """
        for node in self.node_index.values():
            # Calculate relevance based on topic overlap
            if node.node_type in [NodeType.QUESTION, NodeType.ANSWER]:
                node_topics = node.metadata.get('topics', [])
                if node_topics and current_topics:
                    overlap = len(set(node_topics) & set(current_topics))
                    node.relevance_score = overlap / max(len(current_topics), 1)
                else:
                    # Decay relevance over time
                    depth = self._get_node_depth(node)
                    node.relevance_score = max(0.1, 1.0 - (depth * 0.1))

    def _get_node_depth(self, node: ContextNode) -> int:
        """
        Get the depth of a node in the tree.

        Args:
            node: The node to check

        Returns:
            Depth from root
        """
        depth = 0
        current = node
        while current.parent_id:
            depth += 1
            current = self.node_index.get(current.parent_id, self.root)
        return depth

    def merge_context(self, other_context: Dict[str, Any]) -> None:
        """
        Merge context from another source.

        Args:
            other_context: Context dictionary to merge
        """
        # Merge entities
        if 'entities' in other_context:
            for entity_type, values in other_context['entities'].items():
                if entity_type not in self.extracted_info.entities:
                    self.extracted_info.entities[entity_type] = []
                self.extracted_info.entities[entity_type].extend(values)

        # Merge topics
        if 'topics' in other_context:
            self.extracted_info.topics.extend(other_context['topics'])
            # Remove duplicates
            self.extracted_info.topics = list(set(self.extracted_info.topics))

        # Merge constraints
        if 'constraints' in other_context:
            self.extracted_info.constraints.extend(other_context['constraints'])
            self.extracted_info.constraints = list(set(self.extracted_info.constraints))

        # Merge preferences
        if 'preferences' in other_context:
            self.extracted_info.preferences.update(other_context['preferences'])

    def to_json(self) -> str:
        """
        Serialize the context tree to JSON.

        Returns:
            JSON string representation
        """
        def node_to_dict(node: ContextNode) -> Dict:
            return {
                'node_id': node.node_id,
                'node_type': node.node_type.value,
                'content': node.content,
                'timestamp': node.timestamp,
                'metadata': node.metadata,
                'relevance_score': node.relevance_score,
                'children': [node_to_dict(child) for child in node.children]
            }

        tree_dict = {
            'root': node_to_dict(self.root),
            'current_node_id': self.current_node.node_id,
            'turn_count': self.turn_count,
            'extracted_info': asdict(self.extracted_info)
        }

        return json.dumps(tree_dict, indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> 'ContextTree':
        """
        Deserialize a context tree from JSON.

        Args:
            json_str: JSON string representation

        Returns:
            Reconstructed ContextTree
        """
        data = json.loads(json_str)
        tree = cls()

        def dict_to_node(node_dict: Dict, parent: Optional[ContextNode] = None) -> ContextNode:
            node = ContextNode(
                node_id=node_dict['node_id'],
                node_type=NodeType(node_dict['node_type']),
                content=node_dict['content'],
                timestamp=node_dict['timestamp'],
                metadata=node_dict.get('metadata', {}),
                relevance_score=node_dict.get('relevance_score', 1.0),
                parent_id=parent.node_id if parent else None
            )

            tree.node_index[node.node_id] = node

            for child_dict in node_dict.get('children', []):
                child_node = dict_to_node(child_dict, node)
                node.children.append(child_node)

            return node

        tree.root = dict_to_node(data['root'])
        tree.current_node = tree.node_index[data['current_node_id']]
        tree.turn_count = data['turn_count']

        # Reconstruct extracted info
        info_data = data['extracted_info']
        tree.extracted_info = ExtractedInformation(
            entities=info_data['entities'],
            intent=info_data['intent'],
            topics=info_data['topics'],
            constraints=info_data['constraints'],
            preferences=info_data['preferences']
        )

        return tree

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the context tree.

        Returns:
            Summary dictionary
        """
        return {
            'total_nodes': len(self.node_index),
            'depth': self._get_node_depth(self.current_node),
            'turn_count': self.turn_count,
            'extracted_entities': list(self.extracted_info.entities.keys()),
            'current_intent': self.extracted_info.intent,
            'topics': self.extracted_info.topics,
            'constraints': self.extracted_info.constraints
        }