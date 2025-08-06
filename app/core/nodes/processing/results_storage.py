"""Processing results storage node - stores analysis results to database."""

import logging
from sqlalchemy import select

from ...models.messages import SMessage
from ...states import ProcessingState
from ...database.db import get_db
from ...database.schema import (
    TranscriptionProcessing,
    TranscriptionAnalysis,
    TranscriptionInsights
)
from ...database.queries import handle_persistence

logger = logging.getLogger(__name__)


async def results_storage_node(state: ProcessingState):
    """Store analysis and insights results to database"""

    agent_name = "ProcessingResultsStorage"

    transcription_analysis = state["transcription_analysis"]
    extracted_insights = state["extracted_insights"]

    try:
        transcription_id = state["transcription_id"]
        logger.info(
            f"Storing analysis results for transcription {transcription_id}"
        )

        async for db in get_db():
            try:
                # Begin transaction
                await db.begin()

                # Check if processing already exists
                existing_processing = await db.execute(
                    select(TranscriptionProcessing).where(
                        TranscriptionProcessing.transcription_id
                        == transcription_id
                    )
                )
                processing_record = existing_processing.scalar_one_or_none()

                if not processing_record:
                    processing_record = TranscriptionProcessing(
                        transcription_id=transcription_id,
                        status="pending"
                    )
                    db.add(processing_record)
                    # Flush to get the ID but don't commit yet
                    await db.flush()

                analysis_id = processing_record.analysis_id
                insights_id = processing_record.insights_id

                # Handle analysis record
                if transcription_analysis:
                    analysis_changes = await handle_persistence(
                        db=db,
                        table_model=TranscriptionAnalysis,
                        record=dict(transcription_analysis),
                        **({"record_id": analysis_id} if analysis_id else {})
                    )

                    if not analysis_id:
                        analysis_id = analysis_changes["id"]
                        await db.flush()

                        processing_record.analysis_id = analysis_id
                        logger.info(
                            "Created new analysis record for transcription "
                            f"{transcription_id} with id {analysis_id}"
                        )

                # Handle insights record
                if extracted_insights:
                    insights_changes = await handle_persistence(
                        db=db,
                        table_model=TranscriptionInsights,
                        record=dict(extracted_insights),
                        **({"record_id": insights_id} if insights_id else {})
                    )

                    if not insights_id:
                        insights_id = insights_changes["id"]
                        await db.flush()

                        processing_record.insights_id = insights_id
                        logger.info(
                            "Created new insights record for transcription "
                            f"{transcription_id} with id {insights_id}"
                        )

                # Update processing status
                processing_record.status = "completed"
                logger.info(
                    "Updated existing processing for transcription "
                    f"{transcription_id}"
                )

                await db.flush()
                await db.commit()

            except Exception as e:
                # Rollback the entire transaction on any error
                await db.rollback()
                logger.error(
                    "Transaction failed for transcription "
                    f"{transcription_id}, rolling back: {str(e)}"
                )
                raise e

        logger.info(
            "Successfully stored analysis results for transcription "
            f"{transcription_id}"
        )

        return {
            "messages": [
                SMessage(
                    name=agent_name,
                    content=(
                        "Analysis results stored for transcription "
                        f"{transcription_id}"
                    )
                )
            ],
        }

    except Exception as e:
        logger.error(
            "Error storing analysis results for transcription "
            f"{transcription_id}: {str(e)}"
        )

        return {
            "messages": [SMessage(
                name=agent_name,
                content=f"Error storing analysis results: {str(e)}"
            )]
        }
