"""Manually enqueue embedding generation for a specific session."""

import asyncio
import sys
import uuid

from arq import create_pool
from arq.connections import RedisSettings

from pazpaz.workers.settings import QUEUE_NAME, get_redis_settings


async def enqueue_session_embeddings(session_id: str, workspace_id: str):
    """Enqueue embedding generation job for a session."""
    # Create ARQ Redis pool with the correct queue name
    redis_config = get_redis_settings()
    redis_settings = RedisSettings(**redis_config)

    pool = await create_pool(redis_settings, default_queue_name=QUEUE_NAME)

    try:
        # Enqueue the job
        job = await pool.enqueue_job(
            "generate_session_embeddings",
            session_id=session_id,
            workspace_id=workspace_id,
        )

        print(f"✓ Enqueued embedding generation job: {job.job_id}")
        print(f"  Session ID: {session_id}")
        print(f"  Workspace ID: {workspace_id}")

        return job

    finally:
        await pool.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python generate_session_embeddings_manual.py <session_id> <workspace_id>")
        sys.exit(1)

    session_id = sys.argv[1]
    workspace_id = sys.argv[2]

    # Validate UUIDs
    try:
        uuid.UUID(session_id)
        uuid.UUID(workspace_id)
    except ValueError as e:
        print(f"Error: Invalid UUID format: {e}")
        sys.exit(1)

    asyncio.run(enqueue_session_embeddings(session_id, workspace_id))
