#!/bin/bash
#
# Setup script for LAWAST development environment
# Installs all required dependencies for TASK-003 and TASK-004
#

echo "========================================="
echo "LAWAST Environment Setup"
echo "========================================="

# Check if Python 3.8+ is installed
python_version=$(python3 --version 2>&1 | grep -Po '(?<=Python )\d+\.\d+')
required_version="3.8"

if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python 3.8+ is required. Found: Python $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  No virtual environment detected."
    echo "   It's recommended to use a virtual environment."
    echo ""
    echo "   Create one with:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate  # On Linux/Mac"
    echo "   venv\\Scripts\\activate     # On Windows"
    echo ""
    read -p "Continue without virtual environment? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 1
    fi
else
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
fi

# Upgrade pip
echo ""
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "📦 Installing requirements..."
pip install -r requirements.txt

# Check if Neo4j is running
echo ""
echo "🔍 Checking Neo4j..."
if docker ps | grep -q neo4j; then
    echo "✅ Neo4j container is running"
else
    echo "⚠️  Neo4j is not running."
    echo "   Start it with: docker-compose up -d"
fi

# Create necessary directories
echo ""
echo "📁 Creating directory structure..."
mkdir -p data/neo4j
mkdir -p logs
mkdir -p tests

# Set up environment file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file..."
    cat > .env << EOF
# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=lawast2024
NEO4J_DATABASE=neo4j

# Batch Processing
BATCH_SIZE=1000
CHECKPOINT_FILE=processing_checkpoint.json

# Hugging Face (optional)
# HUGGINGFACE_API_KEY=your_key_here
EOF
    echo "✅ Created .env file (please update passwords!)"
else
    echo "✅ .env file exists"
fi

# Run tests
echo ""
echo "🧪 Running tests..."
python -m pytest tests/test_relationship_extractor.py -v --tb=short 2>/dev/null || {
    echo "⚠️  Some tests failed. This might be expected if Neo4j is not populated yet."
}

echo ""
echo "========================================="
echo "✅ Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Ensure Neo4j is running: docker-compose up -d"
echo "2. Initialize Neo4j schema: python scripts/init_neo4j_schema.py"
echo "3. Run TASK-003 to create nodes (when ready)"
echo "4. Run relationship extraction: python scripts/run_relationship_extraction.py --limit 100"
echo ""
echo "For more information, see kanban/in-progress/"