# Service Pattern Reference

Business logic layer that orchestrates repositories and applies domain rules.

## Key Principles

1. **Create repositories in `__init__`** - Services own their repositories
2. **Session as first parameter** - Every method receives session
3. **Business logic here** - Validation, rules, orchestration
4. **No direct SQL** - Use repositories for data access
5. **Raise domain exceptions** - For validation failures

## Basic Service Structure

```python
# api/services/item_service.py
"""Item Service - Business logic for item management."""

from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories.item_repository import ItemRepository
from core.exceptions import NotFoundError, ValidationError, ConflictError
from db.models import Item


class ItemService:
    """Service for item management."""

    def __init__(self):
        """Initialize service with repositories."""
        self._repo = ItemRepository()

    async def create_item(
        self,
        session: AsyncSession,
        name_en: str,
        name_ar: str,
        description_en: Optional[str] = None,
        description_ar: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> Item:
        """
        Create a new item.
        
        Business rules:
        - Name must be unique
        - Category must exist if provided
        """
        # Check for duplicate name
        existing = await self._repo.get_by_name_en(session, name_en)
        if existing:
            raise ConflictError(
                entity="Item",
                field="name_en",
                value=name_en,
            )
        
        # Validate category if provided
        if category_id:
            from api.repositories.category_repository import CategoryRepository
            cat_repo = CategoryRepository()
            category = await cat_repo.get_by_id(session, category_id)
            if not category:
                raise ValidationError(f"Category {category_id} not found")
        
        # Create item
        item = Item(
            name_en=name_en,
            name_ar=name_ar,
            description_en=description_en,
            description_ar=description_ar,
            category_id=category_id,
        )
        return await self._repo.create(session, item)

    async def get_item(self, session: AsyncSession, item_id: int) -> Item:
        """Get an item by ID."""
        item = await self._repo.get_by_id(session, item_id)
        if not item:
            raise NotFoundError(entity="Item", identifier=item_id)
        return item

    async def list_items(
        self,
        session: AsyncSession,
        page: int = 1,
        per_page: int = 25,
        name_filter: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> Tuple[List[Item], int]:
        """List items with pagination and filtering."""
        return await self._repo.list(
            session,
            page=page,
            per_page=per_page,
            name_filter=name_filter,
            is_active=is_active,
        )

    async def update_item(
        self,
        session: AsyncSession,
        item_id: int,
        name_en: Optional[str] = None,
        name_ar: Optional[str] = None,
        description_en: Optional[str] = None,
        description_ar: Optional[str] = None,
    ) -> Item:
        """
        Update an item.
        
        Business rules:
        - Item must exist
        - New name must be unique
        """
        # Check item exists
        item = await self._repo.get_by_id(session, item_id)
        if not item:
            raise NotFoundError(entity="Item", identifier=item_id)
        
        # Check name uniqueness if changing
        if name_en and name_en != item.name_en:
            existing = await self._repo.get_by_name_en(session, name_en)
            if existing:
                raise ConflictError(
                    entity="Item",
                    field="name_en",
                    value=name_en,
                )
        
        # Build update dict
        update_data = {}
        if name_en is not None:
            update_data["name_en"] = name_en
        if name_ar is not None:
            update_data["name_ar"] = name_ar
        if description_en is not None:
            update_data["description_en"] = description_en
        if description_ar is not None:
            update_data["description_ar"] = description_ar
        
        return await self._repo.update(session, item_id, update_data)

    async def update_item_status(
        self,
        session: AsyncSession,
        item_id: int,
        is_active: bool,
    ) -> Item:
        """Toggle item active/inactive status."""
        update_data = {"is_active": is_active}
        return await self._repo.update(session, item_id, update_data)

    async def delete_item(self, session: AsyncSession, item_id: int) -> None:
        """Delete an item."""
        await self._repo.delete(session, item_id)
```

## Multi-Repository Service

```python
class OrderService:
    """Service managing orders with multiple repositories."""

    def __init__(self):
        self._order_repo = OrderRepository()
        self._item_repo = ItemRepository()
        self._customer_repo = CustomerRepository()

    async def create_order(
        self,
        session: AsyncSession,
        customer_id: int,
        item_ids: List[int],
    ) -> Order:
        """
        Create order with validation across entities.
        
        All operations use the SAME session for atomicity.
        """
        # Validate customer
        customer = await self._customer_repo.get_by_id(session, customer_id)
        if not customer:
            raise NotFoundError(entity="Customer", identifier=customer_id)
        
        if not customer.is_active:
            raise ValidationError("Cannot create order for inactive customer")
        
        # Validate items
        items = await self._item_repo.get_by_ids(session, item_ids)
        if len(items) != len(item_ids):
            found_ids = {i.id for i in items}
            missing = set(item_ids) - found_ids
            raise ValidationError(f"Items not found: {missing}")
        
        # Check all items active
        inactive_items = [i for i in items if not i.is_active]
        if inactive_items:
            raise ValidationError(f"Cannot order inactive items: {[i.id for i in inactive_items]}")
        
        # Create order
        order = Order(
            customer_id=customer_id,
            total=sum(item.price for item in items),
        )
        order = await self._order_repo.create(session, order)
        
        # Create order lines
        for item in items:
            line = OrderLine(order_id=order.id, item_id=item.id, price=item.price)
            await self._order_repo.create_line(session, line)
        
        return order
```

## Service with External Dependencies

```python
class UserService:
    """Service with external service dependencies."""

    def __init__(self):
        self._user_repo = UserRepository()
        self._role_repo = RoleRepository()

    async def create_user_with_role(
        self,
        session: AsyncSession,
        username: str,
        role_name: str,
    ) -> User:
        """Create user and assign role in single transaction."""
        # Check username unique
        existing = await self._user_repo.get_by_username(session, username)
        if existing:
            raise ConflictError(entity="User", field="username", value=username)
        
        # Get or create role
        role = await self._role_repo.get_by_name_en(session, role_name)
        if not role:
            raise ValidationError(f"Role '{role_name}' not found")
        
        # Create user
        user = User(username=username)
        user = await self._user_repo.create(session, user)
        
        # Assign role (same session)
        await self._role_repo.assign_to_user(session, user.id, role.id)
        
        return user
```

## Bulk Operations

```python
async def bulk_update_status(
    self,
    session: AsyncSession,
    item_ids: List[int],
    is_active: bool,
) -> int:
    """
    Bulk update item status.
    
    Returns count of updated items.
    """
    # Validate all items exist
    items = await self._repo.get_by_ids(session, item_ids)
    if len(items) != len(item_ids):
        found_ids = {i.id for i in items}
        missing = set(item_ids) - found_ids
        raise ValidationError(f"Items not found: {missing}")
    
    # Filter items already in target state
    to_update = [i.id for i in items if i.is_active != is_active]
    
    if not to_update:
        return 0
    
    return await self._repo.bulk_update_status(session, to_update, is_active)
```

## Validation Helpers

```python
async def _validate_unique_name(
    self,
    session: AsyncSession,
    name_en: str,
    exclude_id: Optional[int] = None,
) -> None:
    """Check name is unique, optionally excluding an ID (for updates)."""
    existing = await self._repo.get_by_name_en(session, name_en)
    if existing and (exclude_id is None or existing.id != exclude_id):
        raise ConflictError(entity="Item", field="name_en", value=name_en)

async def _validate_category_exists(
    self,
    session: AsyncSession,
    category_id: int,
) -> None:
    """Validate category exists and is active."""
    from api.repositories.category_repository import CategoryRepository
    cat_repo = CategoryRepository()
    category = await cat_repo.get_by_id(session, category_id)
    if not category:
        raise ValidationError(f"Category {category_id} not found")
    if not category.is_active:
        raise ValidationError(f"Category {category_id} is inactive")
```

## Service with Logging

```python
import logging

logger = logging.getLogger(__name__)

class AuditedItemService:
    """Service with audit logging."""

    def __init__(self):
        self._repo = ItemRepository()
        self._log_repo = LogItemRepository()

    async def create_item(
        self,
        session: AsyncSession,
        created_by_id: str,
        **kwargs,
    ) -> Item:
        """Create item with audit log."""
        item = Item(**kwargs)
        item = await self._repo.create(session, item)
        
        # Log creation
        await self._log_repo.log_operation(
            session,
            operation_type="create",
            item_id=item.id,
            user_id=created_by_id,
            details={"name_en": item.name_en},
        )
        
        logger.info(f"Item {item.id} created by {created_by_id}")
        return item
```

## Key Points

1. **Repositories in `__init__`** - Service owns its data access
2. **Session as first param** - Consistent with repository pattern
3. **Business rules in service** - Uniqueness, existence, state validation
4. **Same session for multi-repo** - Ensures atomicity
5. **Raise domain exceptions** - ValidationError, ConflictError, NotFoundError
6. **No SQL in service** - All data access through repositories
7. **Return domain objects** - Let endpoint convert to response
