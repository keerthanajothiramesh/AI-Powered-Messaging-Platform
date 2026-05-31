# Design Patterns Used

## 1. Repository Pattern
**Location:** `src/messaging/message_service.py`, `src/notifications/service.py`  
All database operations abstracted behind service functions. Controllers never touch DB directly.

## 2. Observer Pattern (WebSocket Events)
**Location:** `src/messaging/websocket_manager.py`, `src/messaging/websocket_router.py`  
ConnectionManager acts as event bus. Message send triggers delivery to all subscribed WebSocket connections.

## 3. Strategy Pattern (Search)
**Location:** `src/search/search_service.py`  
Pluggable search strategies: BM25 keyword search, ChromaDB semantic search, fused hybrid. Each is swappable.

## 4. Circuit Breaker Pattern
**Location:** `src/ai/gemini_client.py`  
After 3 consecutive Gemini API failures, circuit opens and all calls fall back to local stub. Resets on success.

## 5. Factory Pattern (Agent Creation)
**Location:** `src/agents/orchestrator.py`  
Orchestrator creates the appropriate agent based on intent classification. New agents added without changing orchestrator logic.

## 6. Singleton Pattern (Service Instances)
**Location:** `src/ai/embedding_service.py`, `src/ai/vector_store.py`, `src/messaging/websocket_manager.py`  
Heavy models (sentence-transformers, ChromaDB) loaded once at startup and reused across requests.

## 7. RAG Pattern (Retrieval-Augmented Generation)
**Location:** `src/ai/rag_service.py`  
Retrieve relevant messages from MongoDB/ChromaDB → build context → generate with Gemini. Grounds LLM in actual chat data.

## 8. LLM-as-Judge Pattern
**Location:** `src/agents/judge_agent.py`  
After summarisation agent produces output, a second LLM call evaluates quality (relevance, accuracy, completeness). Triggers regeneration if score < 7/10.

## 9. Multi-Agent Orchestration Pattern
**Location:** `src/agents/orchestrator.py`  
Central orchestrator routes tasks to specialised agents (Search, Summarisation, Moderation, Notification, Delivery) based on intent classification.

## 10. Reciprocal Rank Fusion (RRF)
**Location:** `src/search/search_service.py`  
Combines ranked lists from BM25 and semantic search without needing to tune score weights. Each item gets score = Σ 1/(k + rank).

## 11. Graceful Degradation Pattern
**Location:** `src/ai/gemini_client.py`, `src/search/search_service.py`, `src/media/service.py`  
- Gemini unavailable → local text stub  
- ChromaDB unavailable → BM25-only search  
- S3 unavailable → local uploads/ folder

## 12. Connection Pool Pattern
**Location:** `src/common/database.py`  
asyncpg pool (5-20 connections) and motor client (5-50 connections) maintained across requests to avoid connection overhead.
