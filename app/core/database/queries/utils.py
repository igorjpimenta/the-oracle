import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Any, Dict, Type, Literal, TypedDict
from datetime import datetime

from ..schema import Base

logger = logging.getLogger(__name__)


class RecordChanges(TypedDict):
    """
    Record changes model.
    """
    operation: Literal["create", "update", "delete"]
    id: str
    changes: dict[str, Any]
    has_changes: bool


class PersistenceResult(TypedDict):
    """
    Record changes model.
    """
    operation: Literal["create", "update", "delete"]
    id: str
    changes: Dict[str, Any]
    has_changes: bool


class RecordPersistence:
    @classmethod
    async def get_record_changes(
        cls,
        db: AsyncSession,
        table_model: Type[Base],
        record_dict: Dict[str, Any],
        record_id: str,
        id_field: str
    ) -> RecordChanges:
        """
        Compare a dictionary record with an existing record in a database table
        and return the changes.

        Args:
            db: Database async session
            table_model: SQLAlchemy model class
            record_dict: Dictionary with new record data
            record_id: ID of the record to compare against
            id_field: Name of the ID field (default: "id")

        Returns:
            Dictionary with the following structure:
            {
                "changes": {
                    "field_name": {
                        "old_value": old_value,
                        "new_value": new_value
                    }
                },
                "new_fields": {
                    "field_name": new_value
                },
                "unchanged_fields": ["field1", "field2"],
                "summary": {
                    "total_changes": int,
                    "fields_changed": int,
                    "new_fields_count": int
                }
            }
        """

        # Get the existing record from database
        query = select(table_model) \
            .where(getattr(table_model, id_field) == record_id)
        result = await db.execute(query)
        existing_record = result.scalar_one_or_none()

        if not existing_record:
            logger.warning(
                f"Record with {id_field}={record_id} not found in "
                f"{table_model.__tablename__}. Creating instead."
            )
            with db.no_autoflush:
                db.add(table_model(**record_dict))

            return RecordChanges(
                operation="create",
                id=record_id,
                changes={},
                has_changes=False
            )

        # Convert existing record to dictionary
        existing_dict = cls._convert_record_to_dict(existing_record)

        # Compare records and find changes
        changes, _, _ = cls._compare_field_values(
            record_dict, existing_dict
        )

        return RecordChanges(
            operation="update",
            id=record_id,
            changes=changes,
            has_changes=len(changes) > 0
        )

    @classmethod
    async def get_multiple_records_changes(
        cls,
        db: AsyncSession,
        table_model: Type[Base],
        records_list: list[Dict[str, Any]],
        id_field: str = "id"
    ) -> Dict[str, Any]:
        """
        Compare multiple dictionary records with existing records in a
        database table.

        Args:
            db: Database async session
            table_model: SQLAlchemy model class
            records_list: List of dictionaries with record data
                        (each must contain the id_field)
            id_field: Name of the ID field (default: "id")

        Returns:
            Dictionary with record IDs as keys and change dictionaries
            as values
        """
        results: Dict[str, Any] = {}

        for record_dict in records_list:
            if id_field not in record_dict:
                results[f"record_{len(results)}"] = {
                    "error": f"Missing {id_field} field in record",
                    "changes": {},
                    "new_fields": record_dict,
                    "unchanged_fields": [],
                    "summary": {
                        "total_changes": 0,
                        "fields_changed": 0,
                        "new_fields_count": len(record_dict)
                    }
                }
                continue

            record_id = record_dict[id_field]
            changes = await cls.get_record_changes(
                db, table_model, record_dict, record_id, id_field
            )
            results[str(record_id)] = changes

        return results

    @classmethod
    def _compare_field_values(
        cls,
        record_dict: Dict[str, Any],
        existing_dict: Dict[str, Any]
    ) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Any], list[str]]:
        """
        Compare field values and return changes, new fields, unchanged fields.

        Args:
            record_dict: Dictionary with new record data
            existing_dict: Dictionary with existing record data

        Returns:
            Tuple with changes, new fields, and unchanged fields
        """
        changes = {}
        new_fields = {}
        unchanged_fields = []

        # Check for changes in existing fields
        for field_name, new_value in record_dict.items():
            if field_name in existing_dict:
                old_value = existing_dict[field_name]

                # Handle datetime comparison
                if cls._are_datetime_values_equal(old_value, new_value):
                    unchanged_fields.append(field_name)
                    continue

                # Compare values
                if old_value != new_value:
                    changes[field_name] = {
                        "old_value": old_value,
                        "new_value": new_value
                    }
                else:
                    unchanged_fields.append(field_name)
            else:
                # Field doesn't exist in the table model
                new_fields[field_name] = new_value

        # Check for fields that exist in DB but not in input dict
        for field_name in existing_dict:
            if field_name not in record_dict:
                unchanged_fields.append(field_name)

        return changes, new_fields, unchanged_fields

    @staticmethod
    def _convert_record_to_dict(record: Base) -> Dict[str, Any]:
        """
        Convert SQLAlchemy record to dict with proper datetime handling.

        Args:
            record: SQLAlchemy record

        Returns:
            Dictionary with record data
        """
        result = {}
        for column in record.__table__.columns:
            field_name = column.name
            value = getattr(record, field_name)

            # Handle datetime objects for comparison
            if isinstance(value, datetime):
                result[field_name] = value.isoformat() if value else None
            else:
                result[field_name] = value
        return result

    @staticmethod
    def _are_datetime_values_equal(old_value: Any, new_value: Any) -> bool:
        """Check if two values are equal datetime strings."""
        if not (isinstance(new_value, str) and isinstance(old_value, str)):
            return False

        try:
            if "T" in new_value and ":" in new_value:
                new_dt = datetime.fromisoformat(
                    new_value.replace("Z", "+00:00"))
                old_dt = datetime.fromisoformat(
                    old_value.replace("Z", "+00:00"))
                return abs((new_dt - old_dt).total_seconds()) < 1
        except (ValueError, TypeError):
            pass
        return False
