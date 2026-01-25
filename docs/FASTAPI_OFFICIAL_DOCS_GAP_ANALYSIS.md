# FastAPI Official Documentation Gap Analysis

## Fullstack-Agents vs FastAPI Official Documentation

**Date:** 2026-01-25
**Focus:** Backend (FastAPI) only - areas where official docs are BETTER

---

## What Fullstack-Agents Does WELL (Keep As-Is)

The agents already excel at:

| Feature | Agent/Skill | Quality |
|---------|-------------|---------|
| CRUD entity generation | `generate/fastapi-entity` | Excellent |
| Repository pattern | `skills/fastapi` | Excellent |
| Service layer pattern | `skills/fastapi` | Excellent |
| Single-session-per-request | `skills/fastapi` | Excellent |
| CamelModel JSON responses | `skills/fastapi` | Excellent |
| Domain exceptions | `api/exceptions.py` | Good |
| Project scaffolding | `scaffold/project-fastapi` | Good |
| Celery task generation | `generate/celery-task` | Good |
| Scheduled jobs | `generate/scheduled-job` | Good |
| Security review | `review/security` | Good |
| Bilingual support | Pattern detection | Good |
| Soft delete pattern | Pattern detection | Good |
| Audit fields | Pattern detection | Good |

---

## GAPS: Official FastAPI Docs Are Better

### Priority 1: CRITICAL GAPS (High Impact)

#### 1. File Uploads
**Official Docs:** Complete coverage of `File`, `UploadFile`, multiple files, form+file combo
**Agents:** NOT covered at all

**Recommendation:** Add to `generate/fastapi-entity` agent:
```markdown
### Phase 3: Interactive Dialogue - ADD:

**File Fields**
Does this entity have file uploads?
- [ ] Single file (profile image, document)
- [ ] Multiple files (gallery, attachments)
- [ ] No files

If yes, show:
- Storage: Local / S3 / MinIO
- Validation: file types, max size
```

**Pattern to add (`skills/fastapi/references/file-upload-pattern.md`):**
```python
from fastapi import UploadFile, File
from typing import List

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    session: AsyncSession = Depends(get_session),
):
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "application/pdf"]
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not allowed")

    # Validate file size (10MB max)
    MAX_SIZE = 10 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 10MB)")

    # Save file...
    return {"filename": file.filename, "size": len(contents)}
```

---

#### 2. Testing Patterns
**Official Docs:** Comprehensive testing with TestClient, async tests, dependency overrides
**Agents:** NO testing guidance at all

**Recommendation:** Add `generate/fastapi-tests` agent or enhance `scaffold/project-fastapi`:

**Pattern to add (`skills/fastapi/references/testing-pattern.md`):**
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def async_client():
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
async def test_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

# tests/test_users.py
@pytest.mark.asyncio
async def test_create_user(async_client: AsyncClient):
    response = await async_client.post(
        "/api/v1/users",
        json={"name": "Test User", "email": "test@example.com"}
    )
    assert response.status_code == 201
    assert response.json()["name"] == "Test User"

# Dependency override
def override_get_session():
    return test_session

app.dependency_overrides[get_session] = override_get_session
```

---

#### 3. Form Data Handling
**Official Docs:** `Form()` for HTML form submissions, OAuth2 password flow
**Agents:** NOT covered

**Recommendation:** Add to schema patterns:
```python
from fastapi import Form

@router.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...),
):
    # OAuth2 password flow expects form data, not JSON
    return {"access_token": token, "token_type": "bearer"}
```

---

#### 4. PATCH Operations (Partial Updates)
**Official Docs:** Proper PATCH with `exclude_unset=True`
**Agents:** Only generates PUT (full update)

**Recommendation:** Add PATCH endpoint to entity generation:
```python
# Current: Only PUT
@router.put("/{id}")
async def update_item(id: int, item: ItemUpdate): ...

# Add: PATCH for partial updates
@router.patch("/{id}")
async def partial_update_item(
    id: int,
    item: ItemPatch,  # All fields Optional
    session: AsyncSession = Depends(get_session),
):
    db_item = await service.get_item(session, id)
    update_data = item.model_dump(exclude_unset=True)  # Only sent fields
    for field, value in update_data.items():
        setattr(db_item, field, value)
    await session.commit()
    return db_item
```

---

#### 5. Custom Response Types
**Official Docs:** HTMLResponse, StreamingResponse, FileResponse, RedirectResponse
**Agents:** Only JSON responses

**Recommendation:** Add `skills/fastapi/references/response-types-pattern.md`:
```python
from fastapi.responses import (
    HTMLResponse,
    StreamingResponse,
    FileResponse,
    RedirectResponse
)

# HTML Response
@router.get("/page", response_class=HTMLResponse)
async def get_page():
    return "<html><body>Hello</body></html>"

# File Download
@router.get("/download/{file_id}")
async def download_file(file_id: int):
    return FileResponse(
        path="/path/to/file.pdf",
        filename="document.pdf",
        media_type="application/pdf"
    )

# Streaming Response (large files, real-time)
@router.get("/stream")
async def stream_data():
    async def generate():
        for i in range(100):
            yield f"data: {i}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# Redirect
@router.get("/old-path")
async def redirect():
    return RedirectResponse(url="/new-path", status_code=301)
```

---

### Priority 2: HIGH GAPS (Moderate Impact)

#### 6. Response Headers & Cookies
**Official Docs:** Setting custom headers and cookies in responses
**Agents:** NOT covered

```python
from fastapi import Response

@router.get("/")
async def set_cookie(response: Response):
    response.set_cookie(
        key="session_id",
        value="abc123",
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=3600
    )
    response.headers["X-Custom-Header"] = "value"
    return {"message": "Cookie set"}
```

---

#### 7. Header Parameters
**Official Docs:** Reading custom headers, user-agent, authorization
**Agents:** Only covers Authorization via Depends

```python
from fastapi import Header

@router.get("/items")
async def get_items(
    x_token: str = Header(..., alias="X-Token"),
    user_agent: str = Header(None),
):
    return {"token": x_token, "user_agent": user_agent}
```

---

#### 8. Cookie Parameters
**Official Docs:** Reading cookies directly
**Agents:** NOT covered

```python
from fastapi import Cookie

@router.get("/items")
async def get_items(
    session_id: str = Cookie(None),
    preferences: str = Cookie(None),
):
    return {"session_id": session_id}
```

---

#### 9. Multiple Response Status Codes
**Official Docs:** Documenting multiple possible responses in OpenAPI
**Agents:** Only single response model

```python
from fastapi import status

@router.post(
    "/items",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"model": ItemResponse, "description": "Created"},
        400: {"model": ErrorResponse, "description": "Validation error"},
        409: {"model": ErrorResponse, "description": "Item already exists"},
    }
)
async def create_item(item: ItemCreate):
    ...
```

---

#### 10. Advanced Middleware
**Official Docs:** Custom middleware, request/response timing, logging
**Agents:** NOT covered

```python
from starlette.middleware.base import BaseHTTPMiddleware
import time

class TimingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start = time.time()
        response = await call_next(request)
        process_time = time.time() - start
        response.headers["X-Process-Time"] = str(process_time)
        return response

app.add_middleware(TimingMiddleware)
```

---

#### 11. Path Operation Configuration
**Official Docs:** `deprecated`, `tags`, `summary`, `description`, `operation_id`
**Agents:** Only basic endpoint definition

```python
@router.get(
    "/items",
    tags=["items"],
    summary="Get all items",
    description="Retrieve a paginated list of items with optional filtering.",
    response_description="List of items",
    deprecated=False,
    operation_id="get_items_list",
)
async def get_items(): ...
```

---

### Priority 3: MEDIUM GAPS (Nice to Have)

#### 12. OpenAPI Documentation Customization
**Official Docs:** Custom docs URL, ReDoc, hiding endpoints
**Agents:** NOT covered

```python
app = FastAPI(
    title="My API",
    description="API description with **markdown**",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    openapi_tags=[
        {"name": "users", "description": "User operations"},
        {"name": "items", "description": "Item management"},
    ]
)
```

---

#### 13. Background Tasks (FastAPI Native)
**Official Docs:** `BackgroundTasks` for simple async operations
**Agents:** Only covers Celery (heavy-weight)

```python
from fastapi import BackgroundTasks

def send_email(email: str, message: str):
    # Simulate sending email
    pass

@router.post("/send-notification")
async def send_notification(
    email: str,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(send_email, email, "Hello!")
    return {"message": "Notification queued"}
```

---

#### 14. Request Object Direct Access
**Official Docs:** Accessing raw Request object
**Agents:** NOT covered

```python
from fastapi import Request

@router.get("/info")
async def get_request_info(request: Request):
    return {
        "client_host": request.client.host,
        "url": str(request.url),
        "headers": dict(request.headers),
        "cookies": request.cookies,
    }
```

---

#### 15. Sub-Applications (Mounts)
**Official Docs:** Mounting sub-applications for microservice architecture
**Agents:** NOT covered

```python
from fastapi import FastAPI

main_app = FastAPI()
admin_app = FastAPI()
api_v2 = FastAPI()

main_app.mount("/admin", admin_app)
main_app.mount("/api/v2", api_v2)
```

---

#### 16. OAuth2 Scopes
**Official Docs:** Fine-grained permission scopes
**Agents:** Only basic JWT auth

```python
from fastapi.security import OAuth2PasswordBearer, SecurityScopes

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "users:read": "Read users",
        "users:write": "Create/update users",
        "admin": "Admin access",
    }
)

@router.get("/users")
async def get_users(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
):
    # Check if token has required scopes
    ...
```

---

#### 17. HTTP Basic Auth
**Official Docs:** Simple username/password auth
**Agents:** NOT covered

```python
from fastapi.security import HTTPBasic, HTTPBasicCredentials

security = HTTPBasic()

@router.get("/secure")
async def secure_endpoint(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != "admin" or credentials.password != "secret":
        raise HTTPException(401, "Invalid credentials")
    return {"username": credentials.username}
```

---

### Priority 4: LOW GAPS (Edge Cases)

| Topic | Official Docs | Agents | Recommendation |
|-------|--------------|--------|----------------|
| Dataclasses | Alternative to Pydantic | NOT covered | Low priority |
| Behind a Proxy | X-Forwarded headers | NOT covered | Add to scaffold |
| OpenAPI Callbacks | Webhook documentation | NOT covered | Low priority |
| OpenAPI Webhooks | Webhook implementation | NOT covered | Low priority |
| WSGI Integration | Flask/Django mounting | NOT covered | Low priority |
| SDK Generation | Auto client generation | NOT covered | Consider adding |
| Static Files | Serving static content | NOT covered | Add to scaffold |
| Templates (Jinja2) | Server-side rendering | NOT covered | Low priority for API-first |

---

## Recommended Implementation Priority

### Immediate (Add to existing agents)

1. **File Uploads** - Add to `generate/fastapi-entity` dialogue
2. **PATCH Operations** - Add to `generate/fastapi-entity` endpoints
3. **Multiple Response Codes** - Add to router pattern

### Short Term (New patterns/references)

4. **Testing Patterns** - New `skills/fastapi/references/testing-pattern.md`
5. **Custom Responses** - New `skills/fastapi/references/response-types-pattern.md`
6. **Middleware** - New `skills/fastapi/references/middleware-pattern.md`

### Medium Term (New agents or major updates)

7. **Test Generation Agent** - `generate/fastapi-tests`
8. **Form Data** - Add to entity generation for auth endpoints
9. **Headers/Cookies** - Add to patterns

### Future Consideration

10. Background Tasks (FastAPI native) vs Celery
11. OAuth2 Scopes
12. OpenAPI customization
13. Sub-applications

---

## Summary

| Category | Count | Action |
|----------|-------|--------|
| Critical gaps | 5 | Add immediately |
| High gaps | 6 | Add in next release |
| Medium gaps | 6 | Consider adding |
| Low gaps | 8 | Future consideration |

The fullstack-agents excel at **CRUD generation** and **architecture patterns** but lack coverage for:
- **File handling** (uploads, downloads, streaming)
- **Testing** (completely missing)
- **Response variety** (only JSON)
- **Form data** (OAuth2 password flow)
- **Advanced OpenAPI** (docs customization, multiple responses)
