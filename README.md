# AI-Assisted School Management Dashboard (MVP)

A premium, adaptive school management dashboard built with React (Vite) and FastAPI.

## Key Features

1. **Static Dashboard**: Standard reporting and core operational metrics with Recharts.
2. **Adaptive Hub**: AI-curated insights prioritised by operational severity.
3. **What-If Engine**: Simulate parameter shifts to forecast student risk tier changes.
4. **NL2SQL Copilot**: A secure, read-only chat interface for querying school data.
5. **Actionable Alerts**: System-generated anomalies and risk thresholds.
6. **Periodic Digests**: Bi-weekly narrative summaries of institutional performance.
7. **Observability**: NL2SQL pipeline metrics, performance, and golden tests.

## Setup Instructions (Local without Docker)

### Backend

1. Navigate to the `backend` directory: `cd backend`
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `.\venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. Install dependencies: `pip install -r requirements.txt`
5. Configure `.env`: Set your `GEMINI_API_KEY` in `backend/.env`. (Default MySQL URL is `mysql+aiomysql://root:1234@localhost:3306/school_db`)
6. Seed the database (Generates 5k students): `python -m app.seed`
7. Start the server: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

### Frontend

1. Navigate to the `frontend` directory: `cd frontend`
2. Install dependencies: `npm install`
3. Start the dev server: `npm run dev`

## Setup Instructions (Docker)

1. Ensure Docker and Docker Compose are installed.
2. Add your API keys to your local environment (e.g., `export GEMINI_API_KEY="your_key"`).
3. (You will need to create Dockerfiles for backend and frontend if you choose this route)
4. Run `docker-compose up --build`.
