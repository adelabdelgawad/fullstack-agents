# Repository Pattern Reference

Data access layer for SQLAlchemy operations.

## Key Principles

1. **No session in `__init__`** - Repository is stateless
2. **Session as first parameter** - Every method receives session
3. **Use `flush()` not `commit()`** - Let endpoint handle commit
4. **Use `refresh()` after insert** - Get server-generated values
5. **Raise domain exceptions** - NotFoundError, DatabaseError, etc.

## Basic Repository Structure

```python
# api/repositories/item_repository.py
"""Item Repository - Data access layer for Item entity."""

from typing import List, Optional, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import DatabaseError, NotFoundError
from db.models import Item


class ItemRepository:
    """Repository for Item entity."""

    def __init__(self):
        """Initialize repository (stateless - no session stored)."""
        pass

    async def create(self, session: AsyncSession, item: Item) -> Item:
        """Create a new item."""
        try:
            session.add(item)
            await session.flush()
            await session.refresh(item)  # Get server defaults
            return item
        except IntegrityError as e:
            await session.rollback()
            raise DatabaseError(f"Failed to create item: {str(e)}")

    async def get_by_id(
        self, 
        session: AsyncSession, 
        item_id: int
    ) -> Optional[Item]:
        """Get item by ID."""
        result = await session.execute(
            select(Item).where(Item.id == item_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        session: AsyncSession,
        page: int = 1,
        per_page: int = 25,
        name_filter: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Item], int]:
        """List items with pagination and filtering."""
        from core.pagination import calculate_offset

        # Base query
        query = select(Item)

        # Apply filters
        if name_filter:
            search_term = f"%{name_filter.strip()}%"
            query = query.where(
                or_(
                    Item.name_en.ilike(search_term),
                    Item.name_ar.ilike(search_term)
                )
            )
        
        if is_active is not None:
            query = query.where(Item.is_active == is_active)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = calculate_offset(page, per_page)
        result = await session.execute(
            query.offset(offset).limit(per_page)
        )
        
        return result.scalars().all(), total

    async def update(
        self,
        session: AsyncSession,
        item_id: int,
        update_data: dict,
    ) -> Item:
        """Update an item."""
        item = await self.get_by_id(session, item_id)
        if not item:
            raise NotFoundError(entity="Item", identifier=item_id)

        try:
            for key, value in update_data.items():
                if value is not None and hasattr(item, key):
                    setattr(item, key, value)

            await session.flush()
            await session.refresh(item)
            return item
        except IntegrityError as e:
            await session.rollback()
            raise DatabaseError(f"Failed to update item: {str(e)}")

    async def delete(self, session: AsyncSession, item_id: int) -> None:
        """Delete an item."""
        item = await self.get_by_id(session, item_id)
        if not item:
            raise NotFoundError(entity="Item", identifier=item_id)

        await session.delete(item)
        await session.flush()
```

## Query Patterns

### Get by Unique Field

```python
async def get_by_name_en(
    self, 
    session: AsyncSession, 
    name_en: str
) -> Optional[Item]:
    """Get item by English name."""
    result = await session.execute(
        select(Item).where(Item.name_en == name_en)
    )
    return result.scalar_one_or_none()
```

### Get Multiple by IDs

```python
async def get_by_ids(
    self,
    session: AsyncSession,
    item_ids: List[int],
) -> List[Item]:
    """Get multiple items by IDs."""
    result = await session.execute(
        select(Item).where(Item.id.in_(item_ids))
    )
    return result.scalars().all()
```

### Exists Check

```python
async def exists(
    self,
    session: AsyncSession,
    item_id: int,
) -> bool:
    """Check if item exists."""
    result = await session.execute(
        select(func.count()).where(Item.id == item_id)
    )
    return (result.scalar() or 0) > 0
```

### Upsert Pattern

```python
async def create_or_update(
    self,
    session: AsyncSession,
    item: Item,
) -> Item:
    """Create item or update if exists (by unique field)."""
    existing = await self.get_by_name_en(session, item.name_en)
    
    if existing:
        # Update existing
        for key, value in item.__dict__.items():
            if not key.startswith('_') and key != 'id':
                setattr(existing, key, value)
        await session.flush()
        await session.refresh(existing)
        return existing
    
    # Create new
    return await self.create(session, item)
```

### Soft Delete

```python
async def soft_delete(
    self,
    session: AsyncSession,
    item_id: int,
) -> Item:
    """Soft delete (set is_active=False)."""
    return await self.update(session, item_id, {"is_active": False})
```

### Bulk Operations

```python
async def bulk_update_status(
    self,
    session: AsyncSession,
    item_ids: List[int],
    is_active: bool,
) -> int:
    """Update status for multiple items. Returns count updated."""
    from sqlalchemy import update
    
    result = await session.execute(
        update(Item)
        .where(Item.id.in_(item_ids))
        .values(is_active=is_active)
    )
    await session.flush()
    return result.rowcount
```

### Join Queries

```python
async def get_with_category(
    self,
    session: AsyncSession,
    item_id: int,
) -> Optional[Item]:
    """Get item with category eagerly loaded."""
    from sqlalchemy.orm import selectinload
    
    result = await session.execute(
        select(Item)
        .options(selectinload(Item.category))
        .where(Item.id == item_id)
    )
    return result.scalar_one_or_none()
```

### Complex Filtering

```python
async def list_filtered(
    self,
    session: AsyncSession,
    filters: dict,
    page: int = 1,
    per_page: int = 25,
) -> Tuple[List[Item], int]:
    """List items with complex filtering."""
    query = select(Item)
    
    # Text search
    if filters.get("search"):
        term = f"%{filters['search']}%"
        query = query.where(
            or_(
                Item.name_en.ilike(term),
                Item.name_ar.ilike(term),
                Item.description_en.ilike(term),
            )
        )
    
    # Date range
    if filters.get("created_after"):
        query = query.where(Item.created_at >= filters["created_after"])
    if filters.get("created_before"):
        query = query.where(Item.created_at <= filters["created_before"])
    
    # Category filter
    if filters.get("category_ids"):
        query = query.where(Item.category_id.in_(filters["category_ids"]))
    
    # Boolean filter
    if filters.get("is_active") is not None:
        query = query.where(Item.is_active == filters["is_active"])
    
    # Ordering
    order_by = filters.get("order_by", "created_at")
    order_dir = filters.get("order_dir", "desc")
    order_col = getattr(Item, order_by, Item.created_at)
    query = query.order_by(order_col.desc() if order_dir == "desc" else order_col.asc())
    
    # Count and paginate
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0
    
    offset = (page - 1) * per_page
    result = await session.execute(query.offset(offset).limit(per_page))
    
    return result.scalars().all(), total
```

## Error Handling

```python
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

async def create(self, session: AsyncSession, item: Item) -> Item:
    """Create with comprehensive error handling."""
    try:
        session.add(item)
        await session.flush()
        await session.refresh(item)
        return item
    except IntegrityError as e:
        await session.rollback()
        # Check for specific constraint violations
        if "unique" in str(e).lower():
            raise ConflictError(
                entity="Item",
                field="name_en",
                value=item.name_en,
            )
        raise DatabaseError(f"Integrity error: {str(e)}")
    except SQLAlchemyError as e:
        await session.rollback()
        raise DatabaseError(f"Database error: {str(e)}")
```

## Key Points

1. **No session storage** - Repository is stateless, session passed to methods
2. **Use flush() not commit()** - Transaction managed at endpoint level
3. **Always refresh after create** - Get server-generated values (id, timestamps)
4. **Return Tuple for lists** - (items, total_count) for pagination
5. **Raise domain exceptions** - NotFoundError, ConflictError, DatabaseError
6. **Use scalar_one_or_none()** - For single results, returns None if not found
7. **Use scalars().all()** - For list results
