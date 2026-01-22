"""
Migration script to add multiuser support to existing Minima data.

This script:
1. Migrates Qdrant vector store to add user_id to existing points
2. Migrates filesystem to organize files by user_id
3. SQLite migration happens automatically via storage.py

Run this ONCE after deploying the multiuser update.
"""

import os
import logging
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import PointStruct, Filter, FieldCondition, MatchValue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
QDRANT_HOST = os.environ.get("QDRANT_BOOTSTRAP", "qdrant")
QDRANT_COLLECTION = "mnm_storage"
LOCAL_FILES_PATH = os.environ.get("LOCAL_FILES_PATH")
DEFAULT_USER_ID = "default_user"


def migrate_qdrant():
    """Add user_id to all existing Qdrant points"""
    logger.info("Starting Qdrant migration...")

    try:
        client = QdrantClient(host=QDRANT_HOST)

        # Check if collection exists
        collections = client.get_collections().collections
        collection_names = [col.name for col in collections]

        if QDRANT_COLLECTION not in collection_names:
            logger.warning(f"Collection {QDRANT_COLLECTION} does not exist. Skipping Qdrant migration.")
            return

        # Scroll through all points in batches
        offset = None
        total_updated = 0
        batch_size = 100

        while True:
            points, next_offset = client.scroll(
                collection_name=QDRANT_COLLECTION,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )

            if not points:
                break

            # Update points that don't have user_id
            points_to_update = []
            for point in points:
                if 'user_id' not in point.payload:
                    # Add user_id to payload
                    new_payload = dict(point.payload)
                    new_payload['user_id'] = DEFAULT_USER_ID
                    points_to_update.append((point.id, new_payload))

            # Batch update
            if points_to_update:
                for point_id, payload in points_to_update:
                    client.set_payload(
                        collection_name=QDRANT_COLLECTION,
                        payload={"user_id": DEFAULT_USER_ID},
                        points=[point_id]
                    )
                    total_updated += 1

                logger.info(f"Updated {len(points_to_update)} points in this batch")

            # Check if there are more points
            if next_offset is None:
                break
            offset = next_offset

        logger.info(f"Qdrant migration completed. Updated {total_updated} points with user_id='{DEFAULT_USER_ID}'")

    except Exception as e:
        logger.error(f"Error during Qdrant migration: {e}", exc_info=True)
        raise


def migrate_filesystem():
    """Move existing files to default_user directory"""
    logger.info("Starting filesystem migration...")

    if not LOCAL_FILES_PATH:
        logger.warning("LOCAL_FILES_PATH not set. Skipping filesystem migration.")
        return

    try:
        local_files_path = Path(LOCAL_FILES_PATH)
        if not local_files_path.exists():
            logger.warning(f"Path {local_files_path} does not exist. Skipping filesystem migration.")
            return

        # Create default_user directory
        default_user_dir = local_files_path / DEFAULT_USER_ID
        default_user_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created directory: {default_user_dir}")

        # Move all root-level files to default_user directory
        moved_count = 0
        for item in local_files_path.iterdir():
            # Skip if it's the default_user directory itself or other directories
            if item.is_dir():
                logger.info(f"Skipping directory: {item}")
                continue

            # Move file to default_user directory
            new_path = default_user_dir / item.name

            # Check if file already exists
            if new_path.exists():
                logger.warning(f"File already exists at {new_path}, skipping: {item}")
                continue

            try:
                item.rename(new_path)
                logger.info(f"Moved: {item} -> {new_path}")
                moved_count += 1
            except Exception as e:
                logger.error(f"Error moving file {item}: {e}")

        logger.info(f"Filesystem migration completed. Moved {moved_count} files to '{DEFAULT_USER_ID}/' directory")

    except Exception as e:
        logger.error(f"Error during filesystem migration: {e}", exc_info=True)
        raise


def main():
    """Run all migrations"""
    logger.info("=" * 60)
    logger.info("Starting Multiuser Migration")
    logger.info("=" * 60)

    # Note: SQLite migration happens automatically via storage.py _migrate_schema()
    logger.info("SQLite migration: Will run automatically on application startup")

    # Run Qdrant migration
    logger.info("")
    migrate_qdrant()

    # Run filesystem migration
    logger.info("")
    migrate_filesystem()

    logger.info("")
    logger.info("=" * 60)
    logger.info("Migration completed successfully!")
    logger.info("=" * 60)
    logger.info(f"All existing data has been assigned to user: '{DEFAULT_USER_ID}'")
    logger.info("Application is ready for multiuser support.")


if __name__ == "__main__":
    main()
