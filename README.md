# ProjectX

Secure remote access platform for industrial OT networks (PLCs, HMIs, gateways), powered by ZeroTier. Multi-tenant SaaS with 5-tier role-based access.

Built by **Celestial Infosoft**.

---

## Architecture

| Part | Tech | Location |
|------|------|----------|
| **Backend** | FastAPI REST API (port 8000) | `backend/` |
| **Desktop Client** | PyQt6 GUI (also the gateway agent) | `client/` |
| **Database** | PostgreSQL / SQLite via SQLAlchemy | — |
| **Networking** | ZeroTier encrypted mesh | — |

---

## Setup

### 1. Clone & enter the project
```bash
git clone <your-repo-url>
cd projectx
```

### 2. Create one virtual environment (shared by backend + client)
```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac
```

### 3. Install all dependencies (single file)
```bash
pip install -r requirements.txt
```

### 4. Configure environment
```bash
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
```
Then edit `.env` and set your `DATABASE_URL`, `SECRET_KEY`, etc.

---

## Running

### Start the backend (Terminal 1)
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Start the desktop client (Terminal 2)
```bash
cd client
python main.py
```

> First run seeds a System Owner account: **owner@projectx.io / Admin@123**

---

## Project structure
```
projectx/
├── requirements.txt      ← single dependency list (backend + client)
├── .env                  ← single config (git-ignored)
├── .env.example          ← config template (committed)
├── .gitignore
├── backend/              ← FastAPI API
│   ├── main.py
│   ├── config.py
│   ├── models/  routers/  schemas/  services/
└── client/               ← PyQt6 desktop app
    ├── main.py
    ├── config.py
    ├── windows/  widgets/  services/
```

---

## User Roles
1. **System Owner** — platform admin; creates tenants & activation keys
2. **Master User** — full tenant control (1 per tenant, 2FA required)
3. **Second Master** — co-admin backup (max 2, 2FA required)
4. **Admin User** — assigned devices only
5. **Trusted User** — read-only access to assigned devices
