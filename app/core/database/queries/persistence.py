import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Optional, TypeVar

from ..schema import Base
from .utils import PersistenceResult, RecordPersistence

T = TypeVar("T", bound=Base)


async def handle_persistence(
    db: AsyncSession,
    table_model: type[T],
    record: dict[str, Any],
    record_id: Optional[str] = None,
    id_field: str = "id"
) -> PersistenceResult:
    """
    Handle persistence for a given record.
    """
    id = record_id or str(uuid.uuid4())

    changes = await RecordPersistence.get_record_changes(
        db=db,
        table_model=table_model,
        record_dict=record,
        record_id=id,
        id_field=id_field
    )

    return changes
