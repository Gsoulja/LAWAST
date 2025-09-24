# TASK-008.6: Vector Indexing Module

**Status**: BACKLOG
**Priority**: HIGH
**Type**: feature
**Parent**: TASK-008
**Estimated Effort**: 2 days
**Created**: 2024-01-24

## Description
Create vector embeddings for article content and build searchable vector index. This enables semantic search, similarity matching, and powers the Vector RAG component of LAWAST. Must handle 500K+ articles efficiently.

## Acceptance Criteria
- [ ] Generates embeddings for all articles
- [ ] Supports multi-language content
- [ ] Creates searchable vector index
- [ ] Implements semantic search
- [ ] Batch processing for efficiency
- [ ] Incremental update capability
- [ ] Query response < 100ms
- [ ] Memory efficient chunking
- [ ] All tests pass
- [ ] Documentation complete

## Technical Implementation

### Embedding Pipeline
```python
class VectorIndexingPipeline:
    def __init__(self):
        # Multi-language model
        self.model = SentenceTransformer('multilingual-e5-base')
        self.vector_store = ChromaDB(collection='lawast_articles')
        self.chunk_size = 512  # tokens

    def process_articles(self, articles: List[Article]):
        for batch in chunks(articles, batch_size=100):
            # Generate embeddings
            embeddings = self.generate_embeddings(batch)

            # Store in vector database
            self.store_embeddings(batch, embeddings)

    def generate_embeddings(self, articles):
        # Prepare texts
        texts = []
        for article in articles:
            # Combine title and content
            text = f"{article.title}\n{article.content}"

            # Chunk if too long
            chunks = self.chunk_text(text)
            texts.extend(chunks)

        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True
        )

        return embeddings
```

## Chunking Strategy

### Smart Chunking
```python
def chunk_article(article):
    chunks = []

    # Keep article metadata with each chunk
    base_metadata = {
        'article_uri': article.uri,
        'article_number': article.number,
        'law_uri': article.law_uri,
        'language': article.language
    }

    # Chunk by paragraphs first
    for para_num, paragraph in enumerate(article.paragraphs):
        chunk = {
            'text': paragraph.text,
            'metadata': {
                **base_metadata,
                'paragraph': para_num,
                'type': 'paragraph'
            }
        }
        chunks.append(chunk)

    return chunks
```

## Vector Storage

### ChromaDB Schema
```python
collection = client.create_collection(
    name="lawast_articles",
    metadata={"hnsw:space": "cosine"},
    embedding_function=embedding_function
)

# Add documents
collection.add(
    documents=texts,
    embeddings=embeddings,
    metadatas=metadatas,
    ids=article_ids
)
```

## Search Implementation

### Semantic Search
```python
def semantic_search(query: str, top_k: int = 10):
    # Generate query embedding
    query_embedding = model.encode(query)

    # Search vector store
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=['metadatas', 'documents', 'distances']
    )

    # Post-process results
    return process_search_results(results)
```

### Hybrid Search
```python
def hybrid_search(query: str):
    # Semantic search
    vector_results = semantic_search(query)

    # Keyword search in Neo4j
    keyword_results = graph_search(query)

    # Merge and rerank
    return merge_results(vector_results, keyword_results)
```

## Multi-language Support

### Language-specific Processing
```python
MODELS = {
    'multilingual': 'sentence-transformers/multilingual-e5-base',
    'german': 'sentence-transformers/distiluse-base-multilingual-cased',
    'french': 'sentence-transformers/camembert-base',
    'italian': 'sentence-transformers/xlm-r-bert-base-nli-stsb-mean-tokens'
}

def get_embeddings(text, language='multilingual'):
    model = load_model(MODELS[language])
    return model.encode(text)
```

## Performance Optimization
- Batch processing (100 articles at a time)
- GPU acceleration if available
- Caching frequently accessed embeddings
- Index optimization for fast retrieval
- Async processing for large batches

## Testing Requirements
- Test embedding quality
- Verify search accuracy
- Multi-language search tests
- Performance benchmarks
- Memory usage tests

## Success Metrics
- All articles indexed
- < 100ms query response
- > 85% search relevance
- < 8GB memory for full index