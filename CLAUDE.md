# CLAUDE.md — AI-Powered Messaging Platform

## What Was Built
A full-stack AI-powered messaging platform POC featuring:
- Real-time 1:1 and group messaging via WebSocket
- AI semantic search with hybrid BM25 + pgvector retrieval
- RAG-enabled conversation summarisation using OpenAI GPT-4o-mini
- Multi-agent orchestration (Search, Summarisation, Moderation, Notification, Delivery)
- LLM-as-Judge quality validation for summaries
- Multi-language support (English + Japanese)
- React 18 frontend with 8 screens
- Synthetic dataset: 150 users, 25 groups, 60,000 messages

## Key Technical Decisions
1. **Polyglot persistence**: Neon PostgreSQL + pgvector (users/groups/embeddings) + MongoDB Atlas (messages/events)
2. **Hybrid search**: BM25 + semantic via Reciprocal Rank Fusion — better precision than pure semantic
3. **OpenAI GPT-4o-mini**: Chosen for 1M context window, multilingual support, native function calling
4. **WebSocket**: Full-duplex for <500ms delivery; offline queue via MongoDB TTL index (30 days)
5. **Circuit breaker**: 3 failures → open circuit → fallback to local stub
6. **LangGraph agents**: Intent-routed orchestration with specialized agents

## Architecture Overview
```
Frontend (React 18 + Vite + TailwindCSS)
    ↕ REST + WebSocket
FastAPI Backend (Python 3.12)
    ├── Auth (JWT + bcrypt)
    ├── Messaging (WebSocket + REST)
    ├── AI (Embeddings + pgvector + Gemini + RAG)
    ├── Search (BM25 + Semantic + RRF)
    ├── Agents (Orchestrator → Specialized Agents)
    ├── Media (S3 + local fallback)
    └── Notifications
         ↕
    Neon PostgreSQL (users, groups)
    MongoDB Atlas (messages, media, events)
    Neon PostgreSQL pgvector (embeddings)
    OpenAI API (LLM)
```

## Key Components
| Component | File | Purpose |
|---|---|---|
| FastAPI App | `src/main.py` | App entry point, lifespan management |
| WebSocket Manager | `src/messaging/websocket_manager.py` | Real-time presence + message delivery |
| Embedding Service | `src/ai/embedding_service.py` | sentence-transformers all-MiniLM-L6-v2 |
| Vector Store | `src/ai/vector_store.py` | pgvector operations (cosine similarity via `<=>`) |
| OpenAI Client | `src/ai/gemini_client.py` | LLM with circuit breaker |
| RAG Service | `src/ai/rag_service.py` | Summarisation + catch-up |
| Hybrid Search | `src/search/search_service.py` | BM25 + semantic + RRF |
| Chatbot | `src/ai/chatbot_service.py` | Multi-turn with tool calling |
| Orchestrator | `src/agents/orchestrator.py` | Intent routing to agents |
| Judge Agent | `src/agents/judge_agent.py` | LLM-as-Judge quality validation |

## Design Patterns Used
- Repository Pattern (data access abstraction)
- Observer Pattern (WebSocket event distribution)
- Strategy Pattern (pluggable search strategies)
- Circuit Breaker Pattern (OpenAI API resilience)
- Factory Pattern (agent creation)
- Singleton Pattern (model loading)
- RAG Pattern (retrieval-augmented generation)
- LLM-as-Judge Pattern (quality validation)
- Reciprocal Rank Fusion (result merging)
- Graceful Degradation (multi-level fallbacks)

## Demo Talking Points
1. **Semantic Search**: "Find message where Priya shared the project deadline" → returns exact Priya message about March 31st
2. **Group Summary**: Click "AI Summary" on "Project Launch Team" → 2-week summary with key decisions
3. **Catch-up**: Login as user offline 3 days → structured summary per conversation
4. **Media Search**: "Show renovation images" → retrieves image messages with renovation metadata
5. **Multilingual**: Japanese users send in Japanese, AI responds in Japanese, UI switches language

## Known Limitations (POC vs Production)
- WebSocket horizontal scaling needs Redis pub/sub (currently in-memory)
- pgvector on Neon free tier — needs Pinecone/Weaviate for 100M+ vector production scale
- Single OpenAI API key — production needs load balancing across API keys
- No E2E encryption implemented (architecture noted, not built in POC)
- BM25 corpus loaded from MongoDB on search — needs caching layer for production

## How to Run
```bash
cd messaging-platform
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env           # Fill in your API keys

# Generate dataset
python dataset/generate_dataset.py
python dataset/load_postgres.py
python dataset/load_mongo.py
python dataset/generate_embeddings.py

# Start backend
uvicorn src.main:app --reload --port 8000

# Start frontend (in new terminal)
cd frontend
npm install
npm run dev
```
