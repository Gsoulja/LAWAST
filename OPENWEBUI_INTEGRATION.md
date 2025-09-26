# LAWAST OpenWebUI Integration Guide

This guide explains how to integrate LAWAST with OpenWebUI using two methods:
1. **Pipeline Integration** (Recommended) - Direct integration as OpenWebUI pipeline
2. **REST API Integration** - Connect via OpenAI-compatible API

## Prerequisites

- LAWAST installed with dependencies
- Neo4j database running with Swiss legal data
- HuggingFace API key for Apertus model
- OpenWebUI installed and running

## Method 1: Pipeline Integration (Recommended)

### Step 1: Install LAWAST Pipeline

1. Copy the LAWAST pipeline to OpenWebUI's pipelines directory:

```bash
# Default OpenWebUI pipelines location
cp -r src/interfaces/openwebui/lawast_pipeline.py /path/to/openwebui/pipelines/

# Or if using Docker
docker cp src/interfaces/openwebui/lawast_pipeline.py openwebui:/app/pipelines/
```

2. Set environment variables in OpenWebUI:

```bash
export HUGGINGFACE_API_KEY="your-huggingface-api-key"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="lawast2024"
```

### Step 2: Configure OpenWebUI

1. Go to OpenWebUI Settings
2. Navigate to Pipelines section
3. You should see "LAWAST Swiss Legal AI" in available pipelines
4. Enable the pipeline
5. Configure valves if needed:
   - `ENABLE_RAG`: Enable retrieval (default: true)
   - `ENABLE_REASONING`: Enable reasoning engine (default: true)
   - `INCLUDE_CITATIONS`: Show sources (default: true)

### Step 3: Test Pipeline

In OpenWebUI chat:
```
User: Was ist das Rentenalter in der Schweiz?
Bot: [LAWAST will process and respond with Swiss legal information]
```

## Method 2: REST API Integration

### Step 1: Start LAWAST API Server

```bash
# Navigate to LAWAST directory
cd /home/mxlk/LAWAST

# Activate virtual environment
source venv/bin/activate

# Set environment variables
export HUGGINGFACE_API_KEY="your-huggingface-api-key"

# Start the API server
python -m src.interfaces.api.app

# Or with custom host/port
python -c "from src.interfaces.api.app import run_server; run_server(host='0.0.0.0', port=8000)"
```

The API will be available at:
- API Endpoints: `http://localhost:8000`
- Interactive Docs: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

### Step 2: Configure OpenWebUI to Use LAWAST API

1. Go to OpenWebUI Settings
2. Navigate to Connections
3. Add Custom OpenAI API:
   - **API Base URL**: `http://localhost:8000/v1`
   - **API Key**: `any-value` (not used but required by OpenWebUI)
   - **Model**: `lawast`

4. Save and test connection

### Step 3: Select LAWAST Model

In OpenWebUI chat:
1. Click on model selector
2. Choose "lawast" from available models
3. Start chatting with Swiss legal AI

## Docker Deployment

### Using Docker Compose

Create `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  lawast-api:
    build: .
    container_name: lawast-api
    ports:
      - "8000:8000"
    environment:
      - HUGGINGFACE_API_KEY=${HUGGINGFACE_API_KEY}
      - NEO4J_URI=neo4j://neo4j:7687
      - NEO4J_USER=${NEO4J_USER}
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
    depends_on:
      - neo4j
    networks:
      - lawast-network
    command: python -m src.interfaces.api.app

  openwebui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: openwebui
    ports:
      - "3000:8080"
    volumes:
      - openwebui:/app/backend/data
    environment:
      - OPENAI_API_BASE_URL=http://lawast-api:8000/v1
      - OPENAI_API_KEY=dummy-key
    networks:
      - lawast-network

volumes:
  openwebui:

networks:
  lawast-network:
    external: true
```

Run with:
```bash
docker-compose up -d
```

## Testing the Integration

### Basic Test Queries

1. **Legal Questions in German:**
   - "Was ist das Rentenalter in der Schweiz?"
   - "Welche Rechte haben Arbeitnehmer?"

2. **Legal Questions in French:**
   - "Quel est l'âge de la retraite en Suisse?"
   - "Quels sont les droits des employés?"

3. **Article References:**
   - "Was sagt Artikel 21 des AHVG?"
   - "Erkläre OR 321c"

### Verify Features

- ✅ **Multi-turn Dialogue**: Ask follow-up questions
- ✅ **Citations**: Sources should appear with responses
- ✅ **Confidence Scores**: Confidence level for answers
- ✅ **Session Management**: Context preserved across questions

## Monitoring

### Check API Health
```bash
curl http://localhost:8000/health
```

### View Metrics
```bash
curl http://localhost:8000/metrics
```

### Check Logs
```bash
# API logs
docker logs lawast-api

# Pipeline execution logs
tail -f logs/pipeline.log
```

## Troubleshooting

### Issue: Pipeline not showing in OpenWebUI
- Ensure pipeline file is in correct directory
- Check file permissions
- Restart OpenWebUI service

### Issue: No response from API
- Check Neo4j connection: `docker ps` to verify neo4j is running
- Verify HuggingFace API key is set
- Check API logs for errors

### Issue: Slow responses
- First query may be slow due to model loading
- Check Neo4j performance
- Consider enabling caching in pipeline config

### Issue: No citations in responses
- Verify Neo4j has data: Run `check_database.py`
- Check if embeddings are generated
- Ensure RAG is enabled in configuration

## Configuration Options

### Pipeline Valves (OpenWebUI)

| Valve | Description | Default |
|-------|-------------|---------|
| ENABLE_AGENT | Enable intelligent agent | true |
| ENABLE_RAG | Enable retrieval | true |
| ENABLE_REASONING | Enable reasoning engine | true |
| ENABLE_ARTICULATION | Enable Apertus | true |
| MAX_RESPONSE_LENGTH | Maximum response length | 2000 |
| INCLUDE_CITATIONS | Include sources | true |
| INCLUDE_CONFIDENCE | Show confidence score | true |

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| HUGGINGFACE_API_KEY | API key for Apertus | Yes |
| NEO4J_URI | Neo4j connection URI | Yes |
| NEO4J_USER | Neo4j username | Yes |
| NEO4J_PASSWORD | Neo4j password | Yes |

## Performance Optimization

1. **Enable Caching**: Set `ENABLE_CACHING=true` in pipeline config
2. **Connection Pooling**: Neo4j connection pool is automatically managed
3. **Async Operations**: Pipeline uses async for parallel processing
4. **Graceful Degradation**: Continues working if components fail

## Support

For issues or questions:
- Check logs in `/home/mxlk/LAWAST/logs/`
- Review test scripts in `test_*.py`
- Ensure all dependencies are installed: `pip install -r requirements.txt`

## Next Steps

1. **Fine-tune for your use case**: Adjust weights in RAG configuration
2. **Add more data**: Import additional Swiss legal documents
3. **Customize responses**: Modify articulation templates
4. **Monitor usage**: Set up metrics dashboard