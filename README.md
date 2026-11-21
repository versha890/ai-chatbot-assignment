# AI Chatbot – Full Stack Assignment

An AI-powered chatbot built using React, FastAPI, SQLite, and Groq LLM integration. It supports multiple API keys, fallback handling, response caching, and chat session management.

## 1. Live URLs

- **Frontend:** Pending deployment
- **Backend:** Pending deployment
- **API Documentation:** Pending deployment (`/docs`)

## 2. Run locally: with Docker and without

### Without Docker (Current working setup)

**Prerequisites**
- Python 3.10+
- Node.js and npm
- Groq API keys

**Backend Setup**

```bash
cd backend
python -m venv venv
```

Activate virtual environment on Windows:

```powershell
.\venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create `backend/.env`:

```env
LLM_API_KEYS=your_groq_key_1,your_groq_key_2
LLM_MODEL=groq/openai/gpt-oss-20b
DATABASE_URL=sqlite:///./app.db
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173
ENABLE_FAILURE_SIMULATION=true
```

Start backend:

```bash
python -m uvicorn main:app --reload --port 8000
```

**Frontend Setup**

Open another terminal:

```bash
cd frontend
npm install
```

Create `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Start frontend:

```bash
npm run dev
```

**Local URLs**

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- Swagger API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### With Docker

Dockerfiles, `.dockerignore` files, and `docker-compose.yml` have been created. Docker installation and execution are pending verification.

After installing Docker Desktop and starting Docker Engine, run from the project root:

```bash
docker compose up --build
```

Expected access URLs:

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- API Docs: http://localhost:8000/docs

To stop:

```bash
docker compose down
```

## 3. Design decisions: key fallback, caching, SQLite session storage

### API Key Fallback
- Multiple Groq API keys are configured through environment variables.
- When a key encounters a rate limit or provider error, the backend attempts another available key.
- If all configured keys fail, the backend returns an HTTP 503 response.

### Response Caching
- LiteLLM caching is used to reduce repeated LLM requests.
- Cache matching considers the selected model and complete conversation messages.
- Cached responses are identified using `LLM_CACHE` in response metadata.

### SQLite Session Storage
- SQLite stores chat sessions and messages.
- Every conversation is associated with a session ID.
- Message history is retrieved in chronological order.
- System prompts are excluded from the returned conversation history.

## 4. Verification: how to see failover, cache hits and per-message token usage

### Health Check

```http
GET /health
```

### Chat Endpoint

```http
POST /chat
```

Example request:

```json
{
  "session_id": "test-session-01",
  "message": "Explain frontend and backend development."
}
```

### Cache Verification

- Send an identical message using a new session ID.
- A matching cached response should show `LLM_CACHE`.
- Cached responses should reuse the previous reply and token usage.

### Failover Verification

Use this request header:

```http
x-simulate-failure: key_1=429
```

The backend should attempt the next configured key if the first key is simulated as unavailable.

### Response Metadata

Each chat response includes:

- `resolution_source`
- `model`
- `latency_ms`
- `input_tokens`
- `output_tokens`
- `key_id`
- `fallback_attempts`

These fields provide information about response source, performance, token usage, and fallback attempts.

## 5. Setup Used: your editor and AI tools

| Tool | Technology |
|---|---|
| Code Editor | Visual Studio Code |
| Frontend | React.js, Vite, CSS |
| Backend | Python, FastAPI |
| Database | SQLite |
| LLM Provider | Groq |
| LLM Integration | LiteLLM |
| API Testing | Swagger UI |
| Version Control | Git and GitHub |
| AI Assistance | ChatGPT |
| Containerization | Docker and Docker Compose (setup prepared, testing pending) |

## 6. Bonus features (if any): what you added beyond the requirements and why

- **Custom System Prompt:** Allows users to customize chatbot behavior.
- **New Chat Functionality:** Allows users to start a separate conversation.
- **Responsive UI:** Provides a clean chatbot interface across screen sizes.
- **Error Handling:** Displays readable error messages when API requests fail.

These features improve usability, customization, and the overall chat experience.
