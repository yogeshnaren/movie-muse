# Screenplay SaaS

An open-source, web-based screenplay writing platform aimed at matching Final Draft's professional formatting and collaboration features.

---

## 🏃‍♂️ Quick Start (Docker Compose)

```bash
git clone <repo-url>
cd screenplay-saas
# build & run backend + frontend
docker-compose up --build
```

Visit:
- Backend API → http://localhost:8000/health
- Frontend UI → http://localhost:3000

---

## 🛠️ Local Development

### Backend (FastAPI)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload  # http://localhost:8000
```

### Frontend (React + Vite)
```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

---

## 🧪 Running Tests

```bash
# Backend
pytest

# Frontend
npm run test
```

---

## 📦 Project Layout
```
backend/   # FastAPI + Python domain logic
frontend/  # React 18 + Vite PWA
infra/     # Kubernetes / IaC (future)
```

---

## 🚀 Continuous Integration
Automatic linting and test suites run via GitHub Actions on every push and pull request (see `.github/workflows/ci.yml`).