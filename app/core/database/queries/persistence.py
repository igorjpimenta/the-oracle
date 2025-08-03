from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any

from ..schema import Session
from .utils import PersistenceResult, RecordPersistence


async def handle_session_persistence(
    db: AsyncSession,
    id: str,
    record: dict[str, Any]
) -> PersistenceResult:
    """
    Handle session persistence for a given session ID.
    """
    changes = await RecordPersistence.get_record_changes(
        db=db,
        table_model=Session,
        record_dict=record,
        record_id=id
    )

    return changes
