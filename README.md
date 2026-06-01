# AI-Powered Messaging Platform

A production-grade POC of an AI-powered real-time messaging platform with semantic search, RAG summarisation, multi-agent orchestration, and multi-language support.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│               React 18 + Vite Frontend               │
│  Login │ Chat │ AI Assistant │ Search │ Groups       │
└──────────────────────┬──────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────▼──────────────────────────────┐
│              FastAPI Backend (Python 3.12)            │
│  Auth │ Messaging │ AI │ Search │ Agents │ Media     │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
 ┌─────▼──────┐ ┌─────▼──────┐ ┌───▼────────────────┐
 │   Neon     │ │  MongoDB   │ │  pgvector on Neon  │
 │ PostgreSQL │ │   Atlas    │ │  + OpenAI API      │
 │ users/grps │ │  messages  │ │  + fastembed ONNX  │
 └────────────┘ └────────────┘ └────────────────────┘
```

## Prerequisites

- Python 3.12+
- Node.js 18+
- Neon PostgreSQL account (free tier works)
- MongoDB Atlas account (free tier works)
- Google OpenAI API key (free tier works)

## Installation

### 1. Clone and set up Python environment

```bash
cd messaging-platform
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```env
OPENAI_API_KEY=your-gemini-key
NEON_DATABASE_URL=postgresql+asyncpg://user:pass@host/db
MONGODB_URL=mongodb+srv://user:pass@cluster.mongodb.net/messaging
JWT_SECRET_KEY=your-random-secret-key
```

### 3. Generate and load synthetic dataset

```bash
# Generate 150 users, 25 groups, 60,000 messages
python dataset/generate_dataset.py

# Load into PostgreSQL
python dataset/load_postgres.py

# Load into MongoDB
python dataset/load_mongo.py

# Generate pgvector embeddings and load into Neon PostgreSQL (takes ~10-15 minutes)
python dataset/generate_embeddings.py
```

### 4. Start the backend

```bash
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend available at: http://localhost:5173

## Running the Application

After starting both services, open http://localhost:5173 and:

1. Register a new account or login with a demo account
2. Start chatting in groups or direct messages
3. Click the Bot icon (top right) to open the AI Assistant
4. Use Search (magnifying glass) for hybrid keyword/semantic search

## Sample Usage — Demo Scenarios

### Scenario 1: Semantic Search
```
Open AI Assistant → Type:
"Find the message where Priya shared the project deadline"

Expected output:
"Priya Sharma said: 'The project deadline is confirmed for March 31st, 
please ensure all deliverables are ready'"
```

### Scenario 2: Group Summarisation
```
Join "Project Launch Team" group → Click "AI Summary" in the right panel

Expected output:
• Main topics: project timeline, deliverables, team assignments
• Key decision: March 31 deadline confirmed
• Action items: all deliverables due by March 31
```

### Scenario 3: Catch-up Summary
```
POST /ai/catchup {"hours_offline": 72}

Response: {
  "total_missed": 142,
  "group_summaries": {
    "Project Launch Team": {
      "count": 87,
      "summary": "Team discussed deadline confirmation for March 31..."
    }
  }
}
```

### Scenario 4: Media Search
```
Open AI Assistant → Type:
"Show me all renovation images in the team chat"

Expected output: Grid of image messages with renovation metadata
```

### Scenario 5: Multi-language
```
Japanese user types: "プロジェクトの進捗を教えてください"
AI responds in Japanese automatically
Toggle language flag 🇯🇵/🇬🇧 in top right to switch UI language
```

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/auth/register` | POST | Create account |
| `/auth/login` | POST | Get JWT token |
| `/messages/direct` | POST | Send 1:1 message |
| `/messages/group/{id}` | POST | Send group message |
| `/messages/conversation/{id}` | GET | Get chat history |
| `/groups` | POST | Create group |
| `/groups/me` | GET | My groups |
| `/ai/chat` | POST | AI chatbot |
| `/ai/summarise` | POST | Summarise group |
| `/ai/catchup` | POST | Catch-up summary |
| `/ai/search` | POST | AI-powered search |
| `/search` | POST | Hybrid search |
| `/media/upload` | POST | Upload media |
| `/agents/run` | POST | Run AI agent |
| `/health` | GET | System health |
| `/ws/{user_id}` | WS | WebSocket connection |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Google OpenAI API key |
| `NEON_DATABASE_URL` | Yes | PostgreSQL connection string |
| `MONGODB_URL` | Yes | MongoDB Atlas connection string |
| `JWT_SECRET_KEY` | Yes | Random secret for JWT signing |
| `JWT_EXPIRE_MINUTES` | No | Token expiry (default: 1440) |
| `AWS_ACCESS_KEY_ID` | No | S3 uploads (falls back to local) |
| `AWS_SECRET_ACCESS_KEY` | No | S3 uploads |
| `LOCAL_UPLOADS_PATH` | No | Local uploads folder (default: ./uploads) |
| `LOCAL_UPLOADS_PATH` | No | Local uploads (default: ./uploads) |

## Dataset Schema

### Messages (MongoDB)
| Field | Type | Description |
|---|---|---|
| `message_id` | UUID | Unique identifier |
| `sender_id` | UUID | Sender user ID |
| `receiver_id` | UUID | Recipient (null for groups) |
| `group_id` | UUID | Group ID (null for DMs) |
| `content` | string | Message text |
| `media_type` | enum | text/image/voice/video |
| `delivery_status` | enum | sent/delivered/failed/queued |
| `read_status` | enum | read/unread |
| `reactions` | object | `{"emoji": [user_ids]}` |
| `read_by` | array | User IDs who read (groups) |
| `language` | string | en/ja |
| `timestamp` | datetime | ISO 8601 |

### Extensions Added
- `reactions`: Dict of emoji → list of user_ids who reacted
- `read_by`: List of user_ids for group read tracking
- `language`: Detected language code for multilingual search
- `deleted`: Soft-delete flag

## Running Tests

```bash
# API tests (server must be running)
pytest tests/api/ -v

# Load test (100 concurrent users)
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Evaluation suite
python tests/evaluation/eval_suite.py
```
