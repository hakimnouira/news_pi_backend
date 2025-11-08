#  News PI Backend (FastAPI)

A modern structured backend with:

- JWT authentication
- Role-based access control (RBAC)
- Posts (CRUD)
- Comments (CRUD)
- Swagger authentication using OAuth2 (form-based)
- JSON authentication for real frontend applications

---

## 🏗️ Tech Stack

| Layer | Technology |
|------|------------|
| Backend Framework | FastAPI |
| Auth | JWT (`python-jose`) + password hashing (`passlib[bcrypt_sha256]`) |
| Database ORM | SQLAlchemy |
| DB (dev) | SQLite |
| DB (prod-ready) | PostgreSQL |
| Configuration | Pydantic Settings (`.env`) |

---

## 📂 Project Structure

```
news_pi_backend/
├─ app/
│  ├─ api/
│  │  ├─ deps.py            ← JWT token decoding / current user dependency
│  │  ├─ routes/
│  │  │  ├─ auth.py         ← register, login, OAuth2 token
│  │  │  ├─ users.py        ← get profile, list users
│  │  │  ├─ posts.py        ← post CRUD
│  │  │  ├─ comments.py     ← comment CRUD
│  │  │  └─ roles.py        ← role CRUD (admin only)
│  ├─ core/                 ← config + security (hashing, JWT)
│  ├─ db/                   ← database + seeding
│  ├─ models/               ← ORM models
│  ├─ schemas/              ← request/response validation
│  └─ main.py               ← FastAPI app entrypoint
├─ .env
├─ requirements.txt
├─ README.md
```

---

## ⚙️ Installation (Windows PowerShell)

```powershell
git clone https://github.com/<your-user>/news_pi_backend.git
cd news_pi_backend

python -m venv venv
venv\Scripts\activate

pip install -r requirements.txt

# Fix Windows bcrypt conflict
pip uninstall -y bcrypt passlib
pip install "passlib[bcrypt]==1.7.4" "bcrypt==4.0.1"

uvicorn app.main:app --reload
```

✅ Server runs at → http://127.0.0.1:8000  
✅ Swagger Docs → http://127.0.0.1:8000/docs

---

## 🔐 Authentication Flow

| Endpoint | Input | Used by | Purpose |
|----------|--------|----------|---------|
| `POST /api/v1/auth/login` | JSON `{ email, password }` | ✅ Frontend / Postman | Login normally and get JWT |
| `POST /api/v1/auth/token` | Form (`username`, `password`) | ✅ Swagger UI only | Allows Swagger OAuth2 popup to log you in |

> `/token` exists **ONLY** so Swagger UI can authenticate using the OAuth2 popup.  
> Your frontend always uses `/login` (JSON).

---

### Swagger authentication (OAuth2 automatic JWT)

➡️ Open Swagger: http://127.0.0.1:8000/docs  
➡️ Click **Authorize**  
➡️ Enter:

| Field in Swagger | What to put |
|------------------|-------------|
| username | your user email (ex: `admin@example.com`) |
| password | your password (ex: `admin`) |
| client_id / client_secret | leave empty |

Swagger will call:

```
POST /api/v1/auth/token
Content-Type: application/x-www-form-urlencoded
```

and store the JWT automatically.

Now you can call protected endpoints without copying tokens manually 🚀

---

### JSON login (to be used by frontend)

```
POST /api/v1/auth/login
```

Body:

```json
{
  "email": "user@example.com",
  "password": "mypassword"
}
```

Response contains the JWT:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5...",
  "token_type": "bearer"
}
```

---

## 👤 Roles & Permissions

| Feature | User | Admin |
|--------|------|--------|
| Register / Login | ✅ | ✅ |
| Create Post | ✅ | ✅ |
| Edit/Delete own post | ✅ | ✅ |
| Comment on posts | ✅ | ✅ |
| Edit/Delete own comment | ✅ | ✅ |
| Create roles | ❌ | ✅ |
| Assign/remove roles | ❌ | ✅ |

Admin credentials are created automatically at startup from `.env`.

---

## 🧪 API Testing

### ✅ Create a user
```
POST /api/v1/auth/register
```

```json
{
  "email": "user@example.com",
  "password": "mypassword",
  "is_active": true
}
```

### ✅ Get current logged user
```
GET /api/v1/users/me
```

Requires Authorization header:

```
Authorization: Bearer <token>
```

### ✅ Create a post
```
POST /api/v1/posts/
```

Body:
```json
{
  "title": "Breaking News",
  "content": "FastAPI backend works!"
}
```

---

## ✅ Optional Enhancements (next steps)

- Refresh tokens
- Email confirmation workflow
- Pagination & filtering
- Media upload on posts 
