# 🧠 NEO - Local Knowledge Assistant

A privacy-first, fully local RAG (Retrieval-Augmented Generation) powered developer assistant.

## ✨ Features

- **Hybrid Search**: High accuracy with Keyword + Vector search
- **Local LLM**: Ollama + Qwen2.5, no data sent to the cloud
- **Fast**: Instant response for short queries (fan-friendly)
- **Turkish NLP Support**: Character normalization and stemming
- **Smart Features**: Code duplication detection, interview mode, project summarization

## 🚀 Installation

```bash
# 1. Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install Ollama and pull models
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 4. Create demo data
python create_demo_data.py
python indexer.py

# 5. Run the app
python neo_app.py
