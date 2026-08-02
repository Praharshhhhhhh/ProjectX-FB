# SetuLink

Minimal Router Claim & Activation system with Email OTP authentication.

---

## Architecture

| Part | Tech | Location |
|------|------|----------|
| **Backend** | FastAPI REST API (port 8001) | `backend/` |
| **Database** | SQLite / PostgreSQL via SQLAlchemy | — |
| **Authentication** | JWT Auth with Email OTP | — |

---

## Minimal Feature Set

1. **Email OTP Authentication**: Replaces traditional Google Authenticator TOTP. Verification codes are generated and sent via SMTP.
2. **Router Preparation**: The System Owner prepares routers (router ID, serial number, MAC address) and sends activation keys to customer emails.
3. **Router Claiming**: Master/Second Master users can claim prepared routers for their tenant using the serial number and activation key.
4. **Offline Sync Queue**: Retry failed claims automatically once connectivity returns.

---

## Setup

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure environment
Create a `.env` file in the project root with the following fields:
```env
DATABASE_URL="sqlite:///./setulink.db"
SECRET_KEY="your-secret-key"
FIELD_ENCRYPTION_KEY="your-fernet-encryption-key-for-pending-validations"

# SMTP / Email Configuration
SMTP_HOST="localhost"
SMTP_PORT=587
SMTP_USER=""
SMTP_PASSWORD=""
SMTP_FROM="noreply@setulink.io"
```

### 3. Run database migrations
```bash
cd backend
python -m alembic upgrade head
```

### 4. Start the backend
```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

---

## User Roles
1. **System Owner** — platform admin; prepares routers & activation keys
2. **Master User** — tenant owner; claims routers (OTP required)
3. **Second Master** — co-admin; claims routers (OTP required)
4. **Admin User** — tenant user (OTP required if forced)
5. **Trusted User** — read-only access (OTP required if forced)
