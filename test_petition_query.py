#!/usr/bin/env python3
"""
Debug script for investigating petition query issue.
Query: "Entstehen mir Nachteile wenn ich eine Petition einreiche?"
Expected: Article 33 (Petitionsrecht)
Actual: Article 114 (unemployment insurance)

This script tests the entire RAG pipeline to identify why Article 114
is being prioritized over Article 33.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from data_access.neo4j_connection import Neo4jConnectionManager
from retrieval.vector_search import VectorSearch
from retrieval.graph_search import GraphSearch
from retrieval.hybrid_search import HybridSearch
from retrieval.enhanced_triple_rag import EnhancedTripleRAG, EnhancedTripleRAGConfig
from pipeline.query_pipeline import QueryPipeline, PipelineConfig
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PetitionQueryDebugger:
    """Debug the petition query issue comprehensively"""

    def __init__(self):
        self.query = "Entstehen mir Nachteile wenn ich eine Petition einreiche?"
        self.expected_article = "33"
        self.problematic_article = "114"
        self.connection = Neo4jConnectionManager()
        self.model = SentenceTransformer("intfloat/multilingual-e5-large", device="cpu")

        # Initialize search components
        self.vector_search = VectorSearch(self.connection)
        self.graph_search = GraphSearch(self.connection)
        self.hybrid_search = HybridSearch(self.connection)

        # Initialize Enhanced RAG
        config = EnhancedTripleRAGConfig(
            enable_legal_logic=True,
            legal_language="de",
            vector_weight=0.25,
            graph_weight=0.25,
            legal_logic_weight=0.35,
            hybrid_weight=0.15,
            final_top_k=20
        )
        self.enhanced_rag = EnhancedTripleRAG(config=config, connection=self.connection)

        # Initialize full pipeline
        pipeline_config = PipelineConfig(
            enable_legal_logic=True,
            include_metrics=True,
            include_reasoning_chain=True
        )
        self.pipeline = QueryPipeline(config=pipeline_config)

    def print_header(self, title: str):
        """Print formatted section header"""
        print(f"\n{'='*80}")
        print(f"🔍 {title}")
        print(f"{'='*80}")

    def print_subheader(self, title: str):
        """Print formatted subsection header"""
        print(f"\n{'-'*60}")
        print(f"📊 {title}")
        print(f"{'-'*60}")

    async def check_article_exists(self, article_number: str) -> Dict[str, Any]:
        """Check if article exists in database and get its content"""
        query = """
        MATCH (a:Article {sr_number: '101', number: $article_number})
        RETURN
            a.uri as uri,
            a.number as number,
            a.content_full as content,
            a.content_preview as preview,
            a.embedding IS NOT NULL as has_embedding,
            size(a.embedding) as embedding_size
        """

        with self.connection.get_session() as session:
            result = session.run(query, article_number=article_number)
            record = result.single()

            if record:
                return {
                    "exists": True,
                    "uri": record["uri"],
                    "number": record["number"],
                    "content": record["content"],
                    "preview": record["preview"],
                    "has_embedding": record["has_embedding"],
                    "embedding_size": record["embedding_size"]
                }
            else:
                return {"exists": False}

    async def check_embeddings_quality(self):
        """Check embedding quality for Articles 33 and 114"""
        self.print_subheader("Embedding Quality Analysis")

        # Check both articles
        for article_num in [self.expected_article, self.problematic_article]:
            article_info = await self.check_article_exists(article_num)

            print(f"\n📋 Article {article_num}:")
            if article_info["exists"]:
                print(f"   ✓ Exists in database")
                print(f"   📄 Content preview: {article_info['preview'][:200]}...")
                print(f"   🧠 Has embedding: {article_info['has_embedding']}")
                print(f"   📏 Embedding size: {article_info['embedding_size']}")

                # Check content relevance to petition query
                if article_info["content"]:
                    content = article_info["content"].lower()
                    petition_keywords = ["petition", "petitionsrecht", "nachteile", "behörden"]
                    keyword_matches = [kw for kw in petition_keywords if kw in content]
                    print(f"   🔍 Petition keywords found: {keyword_matches}")
            else:
                print(f"   ❌ Article {article_num} not found in database")

    async def test_vector_search_individual(self):
        """Test vector search on individual indexes"""
        self.print_subheader("Individual Vector Index Testing")

        # Generate query embedding
        query_embedding = self.vector_search.generate_query_embedding(self.query)
        print(f"📊 Query embedding generated (dim: {len(query_embedding)})")

        # Test each index individually
        indexes = [
            "law_embedding_index",
            "article_embedding_index",
            "paragraph_embedding_index",
            "subpoint_embedding_index"
        ]

        all_results = {}

        for index_name in indexes:
            print(f"\n🔍 Testing {index_name}:")
            try:
                results = self.vector_search.search_single_index(
                    query_embedding,
                    index_name,
                    top_k=10,
                    min_score=0.0
                )

                all_results[index_name] = results
                print(f"   Found {len(results)} results")

                # Check for Articles 33 and 114 specifically
                for result in results[:5]:
                    title = result.get('title', 'No title')
                    score = result.get('score', 0)
                    content = result.get('content', '')[:100] + "..." if result.get('content') else ''

                    article_match = ""
                    if "33" in title or "Petition" in title:
                        article_match = " 🎯 EXPECTED ARTICLE!"
                    elif "114" in title:
                        article_match = " ⚠️  PROBLEMATIC ARTICLE"

                    print(f"   • {title} (Score: {score:.3f}){article_match}")
                    if content:
                        print(f"     {content}")

            except Exception as e:
                print(f"   ❌ Error searching {index_name}: {e}")
                all_results[index_name] = []

        return all_results

    async def test_hybrid_search(self):
        """Test hybrid vector+BM25 search"""
        self.print_subheader("Hybrid Vector+BM25 Search Testing")

        try:
            results = await asyncio.get_event_loop().run_in_executor(
                None,
                self.hybrid_search.search,
                self.query,
                15  # top_k
            )

            print(f"🔍 Hybrid search found {len(results)} results")

            for i, result in enumerate(results[:10], 1):
                title = result.title or "No title"
                score = result.combined_score
                vector_score = result.vector_score
                bm25_score = result.bm25_score

                article_match = ""
                if "33" in title or "Petition" in title:
                    article_match = " 🎯 EXPECTED ARTICLE!"
                elif "114" in title:
                    article_match = " ⚠️  PROBLEMATIC ARTICLE"

                print(f"   {i:2d}. {title}{article_match}")
                print(f"       Combined: {score:.3f} | Vector: {vector_score:.3f} | BM25: {bm25_score:.3f}")

            return results

        except Exception as e:
            print(f"   ❌ Hybrid search error: {e}")
            return []

    async def test_enhanced_triple_rag(self):
        """Test the full Enhanced Triple RAG system"""
        self.print_subheader("Enhanced Triple RAG Testing")

        try:
            results, metrics = await asyncio.get_event_loop().run_in_executor(
                None,
                self.enhanced_rag.search,
                self.query
            )

            print(f"🔍 Enhanced RAG found {len(results)} results")
            print(f"⏱️  Total search time: {metrics.total_time:.2f}s")
            print(f"📊 Component times:")
            print(f"   • Vector: {metrics.vector_time:.2f}s ({metrics.vector_count} results)")
            print(f"   • Graph: {metrics.graph_time:.2f}s ({metrics.graph_count} results)")
            print(f"   • Legal Logic: {metrics.legal_logic_time:.2f}s ({metrics.legal_logic_count} results)")
            print(f"   • Hybrid: {metrics.hybrid_time:.2f}s ({metrics.hybrid_count} results)")
            print(f"   • Merge: {metrics.merge_time:.2f}s")

            print(f"\n📋 Top {min(10, len(results))} merged results:")
            for i, result in enumerate(results[:10], 1):
                title = result.title or "No title"
                score = result.final_score

                article_match = ""
                if "33" in title or "Petition" in title:
                    article_match = " 🎯 EXPECTED ARTICLE!"
                elif "114" in title:
                    article_match = " ⚠️  PROBLEMATIC ARTICLE"

                print(f"   {i:2d}. {title} (Score: {score:.3f}){article_match}")

                # Show component scores
                components = []
                if hasattr(result, 'vector_score') and result.vector_score > 0:
                    components.append(f"Vector: {result.vector_score:.3f}")
                if hasattr(result, 'graph_score') and result.graph_score > 0:
                    components.append(f"Graph: {result.graph_score:.3f}")
                if hasattr(result, 'legal_logic_score') and result.legal_logic_score > 0:
                    components.append(f"Logic: {result.legal_logic_score:.3f}")
                if hasattr(result, 'hybrid_score') and result.hybrid_score > 0:
                    components.append(f"Hybrid: {result.hybrid_score:.3f}")

                if components:
                    print(f"       Components: {' | '.join(components)}")

            return results, metrics

        except Exception as e:
            print(f"   ❌ Enhanced RAG error: {e}")
            return [], None

    async def test_full_pipeline(self):
        """Test the complete query pipeline"""
        self.print_subheader("Full Pipeline Testing")

        try:
            result = await self.pipeline.execute(self.query)

            print(f"✅ Pipeline execution completed")
            print(f"⏱️  Execution time: {result.execution_time:.2f}s")
            print(f"🎯 Confidence: {result.confidence:.1%}")
            print(f"📄 Answer length: {len(result.answer)} characters")

            if result.citations:
                print(f"\n📚 Citations ({len(result.citations)}):")
                for i, citation in enumerate(result.citations[:5], 1):
                    source = citation.source or "Unknown source"
                    reference = citation.reference or "No reference"
                    relevance = citation.relevance if hasattr(citation, 'relevance') else 0

                    article_match = ""
                    if "33" in source or "33" in reference:
                        article_match = " 🎯 EXPECTED!"
                    elif "114" in source or "114" in reference:
                        article_match = " ⚠️  PROBLEMATIC"

                    print(f"   {i}. {source} - {reference} (Relevance: {relevance:.3f}){article_match}")

            print(f"\n📝 Generated Answer:")
            print(f"   {result.answer[:300]}{'...' if len(result.answer) > 300 else ''}")

            if result.errors:
                print(f"\n❌ Errors: {result.errors}")
            if result.warnings:
                print(f"\n⚠️  Warnings: {result.warnings}")

            return result

        except Exception as e:
            print(f"   ❌ Pipeline error: {e}")
            return None

    async def analyze_scoring_differences(self, vector_results: Dict, hybrid_results: List, enhanced_results: List):
        """Analyze why different components score articles differently"""
        self.print_subheader("Scoring Analysis")

        # Find Articles 33 and 114 in different result sets
        target_articles = {"33": {}, "114": {}}

        # Check vector results
        for index_name, results in vector_results.items():
            for result in results:
                title = result.get('title', '')
                if "33" in title:
                    target_articles["33"][f"vector_{index_name}"] = result.get('score', 0)
                elif "114" in title:
                    target_articles["114"][f"vector_{index_name}"] = result.get('score', 0)

        # Check hybrid results
        for result in hybrid_results:
            title = result.title or ''
            if "33" in title:
                target_articles["33"]["hybrid"] = result.combined_score
                target_articles["33"]["hybrid_vector"] = result.vector_score
                target_articles["33"]["hybrid_bm25"] = result.bm25_score
            elif "114" in title:
                target_articles["114"]["hybrid"] = result.combined_score
                target_articles["114"]["hybrid_vector"] = result.vector_score
                target_articles["114"]["hybrid_bm25"] = result.bm25_score

        # Check enhanced results
        for result in enhanced_results:
            title = result.title or ''
            if "33" in title:
                target_articles["33"]["enhanced_final"] = result.final_score
                if hasattr(result, 'vector_score'):
                    target_articles["33"]["enhanced_vector"] = result.vector_score
                if hasattr(result, 'graph_score'):
                    target_articles["33"]["enhanced_graph"] = result.graph_score
                if hasattr(result, 'legal_logic_score'):
                    target_articles["33"]["enhanced_logic"] = result.legal_logic_score
            elif "114" in title:
                target_articles["114"]["enhanced_final"] = result.final_score
                if hasattr(result, 'vector_score'):
                    target_articles["114"]["enhanced_vector"] = result.vector_score
                if hasattr(result, 'graph_score'):
                    target_articles["114"]["enhanced_graph"] = result.graph_score
                if hasattr(result, 'legal_logic_score'):
                    target_articles["114"]["enhanced_logic"] = result.legal_logic_score

        # Print analysis
        for article_num, scores in target_articles.items():
            if scores:
                print(f"\n📊 Article {article_num} scoring across components:")
                for component, score in scores.items():
                    print(f"   • {component:20s}: {score:.4f}")
            else:
                print(f"\n📊 Article {article_num}: Not found in any results")

    async def search_for_petition_keywords(self):
        """Search database for petition-related content"""
        self.print_subheader("Petition Keywords Search")

        # Search for petition-related content in database
        query = """
        MATCH (n)
        WHERE n.content_full IS NOT NULL
        AND (
            toLower(n.content_full) CONTAINS 'petition' OR
            toLower(n.content_full) CONTAINS 'petitionsrecht' OR
            toLower(n.content_full) CONTAINS 'nachteile' OR
            toLower(n.content_full) CONTAINS 'behörden'
        )
        RETURN
            labels(n)[0] as node_type,
            n.uri as uri,
            n.number as number,
            n.sr_number as sr_number,
            substring(n.content_full, 0, 200) as content_preview
        LIMIT 10
        """

        with self.connection.get_session() as session:
            results = session.run(query)
            records = list(results)

            print(f"🔍 Found {len(records)} nodes with petition-related keywords:")
            for record in records:
                node_type = record["node_type"]
                number = record["number"] or "N/A"
                sr_number = record["sr_number"] or "N/A"
                content = record["content_preview"]

                print(f"   • {node_type} {number} (SR {sr_number})")
                print(f"     {content}...")
                print()

    async def generate_debug_report(self):
        """Generate comprehensive debug report"""
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "query": self.query,
            "expected_article": self.expected_article,
            "problematic_article": self.problematic_article,
            "findings": {}
        }

        self.print_header("PETITION QUERY DEBUG ANALYSIS")
        print(f"🔍 Query: {self.query}")
        print(f"🎯 Expected: Article {self.expected_article} (Petitionsrecht)")
        print(f"⚠️  Problem: Article {self.problematic_article} being returned instead")

        # 1. Check article existence and embeddings
        await self.check_embeddings_quality()

        # 2. Search for petition keywords
        await self.search_for_petition_keywords()

        # 3. Test vector search components
        vector_results = await self.test_vector_search_individual()
        report_data["findings"]["vector_results"] = vector_results

        # 4. Test hybrid search
        hybrid_results = await self.test_hybrid_search()

        # 5. Test enhanced triple RAG
        enhanced_results, enhanced_metrics = await self.test_enhanced_triple_rag()

        # 6. Test full pipeline
        pipeline_result = await self.test_full_pipeline()

        # 7. Analyze scoring differences
        await self.analyze_scoring_differences(vector_results, hybrid_results, enhanced_results)

        # 8. Generate recommendations
        self.print_subheader("Recommendations")
        print("Based on the analysis, consider:")
        print("1. 🔍 Check if Article 33 embeddings are properly generated")
        print("2. 📊 Verify embedding model consistency across pipeline")
        print("3. ⚖️  Review component weights in Enhanced Triple RAG")
        print("4. 🎯 Consider adding petition-specific keywords to boost relevance")
        print("5. 🧠 Check Legal Logic AST for petition-related logic")
        print("6. 📈 Consider adjusting minimum confidence thresholds")

        # Save detailed report
        report_file = f"petition_debug_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)

        print(f"\n📄 Detailed report saved to: {report_file}")

        return report_data


async def main():
    """Main debug execution"""
    debugger = PetitionQueryDebugger()

    try:
        await debugger.generate_debug_report()
    except Exception as e:
        logger.error(f"Debug execution failed: {e}")
        raise
    finally:
        # Cleanup connections
        if hasattr(debugger, 'connection'):
            debugger.connection.close()


if __name__ == "__main__":
    asyncio.run(main())