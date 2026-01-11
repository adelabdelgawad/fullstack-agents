# Router Pattern Reference

API endpoints with FastAPI using dependency injection.

## Key Principles

1. **Always declare session dependency** - `session: AsyncSession = Depends(get_session)`
2. **Instantiate service directly** - `service = ItemService()`
3. **Pass session to service** - `await service.method(session, ...)`
4. **Use response_model** - For automatic validation and documentation
5. **Let exceptions propagate** - Exception handlers convert to HTTP

## Basic Router Structure

```python
# api/v1/items.py
"""Item Endpoints - CRUD operations for items."""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_session
from api.schemas.item_schemas import (
    ItemCreate,
    ItemUpdate,
    ItemResponse,
    ItemStatusUpdate,
)
from api.services.item_service import ItemService
from core.exceptions import NotFoundError, ConflictError, ValidationError

router = APIRouter(prefix="/items", tags=["items"])


# CREATE
@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item(
    item_create: ItemCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Create a new item.
    
    - **name_en**: English name (required)
    - **name_ar**: Arabic name (required)
    - **description_en**: English description (optional)
    - **description_ar**: Arabic description (optional)
    """
    service = ItemService()
    item = await service.create_item(
        session,
        name_en=item_create.name_en,
        name_ar=item_create.name_ar,
        description_en=item_create.description_en,
        description_ar=item_create.description_ar,
    )
    return ItemResponse.model_validate(item)


# READ (single)
@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get item by ID."""
    service = ItemService()
    item = await service.get_item(session, item_id)
    return ItemResponse.model_validate(item)


# READ (list)
@router.get("", response_model=List[ItemResponse])
async def list_items(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(25, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(None, description="Search in name"),
    is_active: Optional[bool] = Query(None, description="Filter by status"),
    session: AsyncSession = Depends(get_session),
):
    """
    List items with pagination and filtering.
    
    Returns paginated list of items matching filters.
    """
    service = ItemService()
    items, total = await service.list_items(
        session,
        page=page,
        per_page=per_page,
        name_filter=search,
        is_active=is_active,
    )
    return [ItemResponse.model_validate(item) for item in items]


# UPDATE
@router.put("/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    item_update: ItemUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update an existing item."""
    service = ItemService()
    item = await service.update_item(
        session,
        item_id=item_id,
        name_en=item_update.name_en,
        name_ar=item_update.name_ar,
        description_en=item_update.description_en,
        description_ar=item_update.description_ar,
    )
    return ItemResponse.model_validate(item)


# UPDATE STATUS
@router.put("/{item_id}/status", response_model=ItemResponse)
async def update_item_status(
    item_id: int,
    status_update: ItemStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Toggle item active/inactive status."""
    service = ItemService()
    item = await service.update_item_status(
        session,
        item_id=item_id,
        is_active=status_update.is_active,
    )
    return ItemResponse.model_validate(item)


# DELETE
@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Delete an item."""
    service = ItemService()
    await service.delete_item(session, item_id)
```

## Authentication Required Endpoints

```python
from utils.security import require_admin, require_super_admin

@router.post(
    "/admin/items",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_item_admin(
    item_create: ItemCreate,
    session: AsyncSession = Depends(get_session),
    payload: dict = Depends(require_admin),  # Requires admin role
):
    """Create item (admin only)."""
    service = ItemService()
    item = await service.create_item(
        session,
        name_en=item_create.name_en,
        name_ar=item_create.name_ar,
        created_by_id=payload["user_id"],  # Use auth payload
    )
    return ItemResponse.model_validate(item)


@router.delete(
    "/admin/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_item_admin(
    item_id: int,
    session: AsyncSession = Depends(get_session),
    _: dict = Depends(require_super_admin),  # Requires super admin
):
    """Delete item (super admin only)."""
    service = ItemService()
    await service.delete_item(session, item_id)
```

## Locale-Aware Endpoints

```python
from fastapi import Request
from settings import settings

def get_locale_from_request(request: Request) -> str:
    """Extract locale from JWT or Accept-Language header."""
    # Try JWT payload first (no DB query)
    refresh_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if refresh_token:
        payload = verify_refresh_token(refresh_token)
        if payload and "locale" in payload:
            return payload["locale"]
    
    # Fallback to Accept-Language
    accept_lang = request.headers.get("accept-language", "")
    if "ar" in accept_lang.lower():
        return "ar"
    return "en"


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item_localized(
    request: Request,
    item_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Get item with locale-aware name."""
    service = ItemService()
    locale = get_locale_from_request(request)
    
    item = await service.get_item(session, item_id)
    
    # Add computed locale field
    response = ItemResponse.model_validate(item)
    response.name = item.get_name(locale)
    response.description = item.get_description(locale)
    
    return response
```

## Bulk Operations

```python
from pydantic import BaseModel
from typing import List

class BulkStatusUpdate(BaseModel):
    item_ids: List[int]
    is_active: bool


@router.post("/bulk/status", response_model=dict)
async def bulk_update_status(
    update: BulkStatusUpdate,
    session: AsyncSession = Depends(get_session),
    payload: dict = Depends(require_admin),
):
    """Bulk update item status."""
    service = ItemService()
    count = await service.bulk_update_status(
        session,
        item_ids=update.item_ids,
        is_active=update.is_active,
    )
    return {"updated_count": count}
```

## Paginated Response with Metadata

```python
from api.schemas._base import CamelModel
from core.pagination import calculate_pagination_metadata

class ItemListResponse(CamelModel):
    items: List[ItemResponse]
    total: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_previous: bool


@router.get("/paginated", response_model=ItemListResponse)
async def list_items_paginated(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List items with pagination metadata."""
    service = ItemService()
    items, total = await service.list_items(session, page=page, per_page=per_page)
    
    meta = calculate_pagination_metadata(total, page, per_page)
    
    return ItemListResponse(
        items=[ItemResponse.model_validate(i) for i in items],
        total=meta.total_count,
        page=meta.page,
        per_page=meta.page_size,
        total_pages=meta.total_pages,
        has_next=meta.has_next,
        has_previous=meta.has_previous,
    )
```

## Multiple Services in One Endpoint

```python
@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(
    order_data: OrderCreate,
    session: AsyncSession = Depends(get_session),
    payload: dict = Depends(require_admin),
):
    """
    Create order with validation across services.
    
    All services use the SAME session for atomicity.
    """
    order_service = OrderService()
    item_service = ItemService()
    customer_service = CustomerService()
    
    # Validate customer
    customer = await customer_service.get_customer(
        session, 
        order_data.customer_id
    )
    
    # Validate items
    for item_id in order_data.item_ids:
        await item_service.get_item(session, item_id)
    
    # Create order (same session)
    order = await order_service.create_order(
        session,
        customer_id=order_data.customer_id,
        item_ids=order_data.item_ids,
        created_by_id=payload["user_id"],
    )
    
    return OrderResponse.model_validate(order)
```

## Router Registration in app.py

```python
# app.py
from fastapi import FastAPI
from api.v1 import items, orders, customers
from api.exception_handlers import register_exception_handlers

app = FastAPI(title="My API")

# Register exception handlers
register_exception_handlers(app)

# Register routers
app.include_router(items.router, prefix="/api/v1")
app.include_router(orders.router, prefix="/api/v1")
app.include_router(customers.router, prefix="/api/v1")
```

## Key Points

1. **Always include session dependency** - Required for single-session-per-request
2. **Instantiate service in endpoint** - Not as dependency
3. **Pass session to every service call** - First parameter
4. **Use response_model** - Automatic validation and docs
5. **Let exceptions propagate** - Exception handlers do the work
6. **Use Query() for params** - Adds validation and docs
7. **HTTP status codes** - 201 for create, 204 for delete
