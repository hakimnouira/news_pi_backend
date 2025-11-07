# news_pi_backend# 🚀 News PI Backend (FastAPI)

A modern backend built with **FastAPI**, implementing:

- Authentication (JWT)
- Users & Roles (RBAC)
- Posts (CRUD)
- Comments (CRUD)
- Role-based permissions (Admin / User)

Perfect foundation to attach a frontend (React / Angular / Next.js / Vue).

---

## 🏗️ Tech Stack

| Component | Technology |
|----------|------------|
| API Framework | **FastAPI** |
| ORM / Database layer | **SQLAlchemy** |
| Auth | JWT (`python-jose`), hashing (`passlib[bcrypt_sha256]`) |
| DB | SQLite (dev), PostgreSQL (prod-ready) |
| Config | Pydantic / `.env` |
| Migration-ready | Alembic compatible |

---

## 📂 Project Structure

```
news_pi_backend/
├─ app/
│  ├─ api/
│  │  ├─ deps.py
│  │  ├─ routes/
│  │  │  ├─ auth.py       ← login, register, JWT
│  │  │  ├─ users.py      ← get current user, list users
│  │  │  ├─ posts.py      ← users create/edit/delete posts
│  │  │  ├─ comments.py   ← users comment on posts
│  │  │  └─ roles.py      ← admin manage roles
│  ├─ core/               ← config + security (jwt, hashing)
│  ├─ db/                 ← database + seeding (admin + roles)
│  ├─ models/             ← SQLAlchemy models
│  ├─ schemas/            ← Pydantic request/response models
│  └─ main.py             ← app entrypoint
├─ .env.example
├─ .gitignore
├─ requirements.txt
├─ README.md
```

---

## ⚙️ Setup (Windows / PowerShell)

```powershell
# 1. Clone project
git clone https://github.com/<your-user>/news_pi_backend.git
cd news_pi_backend

# 2. Create and activate venv
python -m venv venv
.env\Scriptsctivate

# 3. Install dependencies
pip install -r requirements.txt

# Fix Windows bcrypt issue
pip uninstall -y bcrypt passlib
pip install "passlib[bcrypt]==1.7.4" "bcrypt==4.0.1"

# 4. Run server
uvicorn app.main:app --reload
```

✅ Backend is running at:  
👉 http://127.0.0.1:8000  
Swagger Docs: http://127.0.0.1:8000/docs

---

## 🔐 Environment Variables

Copy `.env.example → .env`

```
API_V1_STR=/api/v1
SECRET_KEY=YOUR_SECRET
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DATABASE_URL=sqlite:///./app.db

FIRST_SUPERUSER_EMAIL=admin@example.com
FIRST_SUPERUSER_PASSWORD=admin
```

> On first launch, backend creates admin & default roles (`admin`, `user`).

---

## 👤 Roles & Permissions

| Feature | User | Admin |
|---------|------|--------|
| Register / Login | ✅ | ✅ |
| Create Posts | ✅ | ✅ |
| Edit / Delete **own** posts | ✅ | ✅ |
| Create Comments | ✅ | ✅ |
| Edit / Delete **own** comments | ✅ | ✅ |
| Assign roles to users | ❌ | ✅ |
| Create/delete roles | ❌ | ✅ |
| View list of users | ✅ | ✅ |
| View all posts/comments | ✅ | ✅ |

---

## 🧪 Testing Endpoints via Swagger

➡️ Open: http://127.0.0.1:8000/docs

### ✅ Register user (`POST /api/v1/auth/register`)

```json
{
  "email": "user@example.com",
  "password": "mypassword",
  "is_active": true
}
```

### ✅ Login (`POST /api/v1/auth/login`)

```json
{
  "email": "user@example.com",
  "password": "mypassword"
}
```

Copy the token → Click **Authorize** → paste:

```
Bearer eyJ...
```

### ✅ Get current user (`GET /api/v1/users/me`)

Response example:

```json
{
  "id": 2,
  "email": "user@example.com",
  "is_active": true,
  "roles": [
    { "id": 2, "name": "user" }
  ]
}
```

---

## 📰 Posts API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/posts/` | ❌ | List posts |
| `POST` | `/api/v1/posts/` | ✅ | Create post |
| `PUT` | `/api/v1/posts/{post_id}` | ✅ (owner only) | Update own post |
| `DELETE` | `/api/v1/posts/{post_id}` | ✅ (owner only) | Delete own post |

Example body:

```json
{
  "title": "Breaking News",
  "content": "FastAPI backend complete!"
}
```

---

## 💬 Comments API

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/v1/comments/` | ❌ | List comments |
| `GET` | `/api/v1/comments/post/{post_id}` | ❌ | List comments on post |
| `POST` | `/api/v1/comments/post/{post_id}` | ✅ | Add comment |
| `PUT` | `/api/v1/comments/{comment_id}` | ✅ (owner) | Edit own comment |
| `DELETE` | `/api/v1/comments/{comment_id}` | ✅ (owner) | Delete own comment |

---

## 🛡️ Roles API (Admin only)

| Method | Endpoint |
|--------|----------|
| `POST /api/v1/roles/` | Create role |
| `DELETE /api/v1/roles/{role_id}` | Delete role |
| `POST /api/v1/roles/assign/{user_id}/{role_name}` | Assign role to user |

---

## ✅ TODO

- Pagination for posts & comments
- Email verification flow
- Refresh tokens
- Pytest test suite

---

MIT License.
