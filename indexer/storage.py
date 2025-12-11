import logging
from sqlmodel import Field, Session, SQLModel, create_engine, select

from singleton import Singleton
from enum import Enum

logger = logging.getLogger(__name__)


class IndexingStatus(Enum):
    new_file = 1
    need_reindexing = 2
    no_need_reindexing = 3


class FileStatus(str, Enum):
    uploaded = "uploaded"
    indexing = "indexing"
    indexed = "indexed"
    failed = "failed"


class MinimaDoc(SQLModel, table=True):
    fpath: str = Field(primary_key=True)
    last_updated_seconds: int | None = Field(default=None, index=True)
    indexing_time_seconds: float | None = Field(default=None)
    status: str = Field(default=FileStatus.uploaded)


class MinimaDocUpdate(SQLModel):
    fpath: str | None = None
    last_updated_seconds: int | None = None
    indexing_time_seconds: float | None = None
    status: str | None = None


sqlite_file_name = "/indexer/storage/database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


class MinimaStore(metaclass=Singleton):

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(engine)
        # Run migration to add new columns if they don't exist
        MinimaStore._migrate_schema()

    @staticmethod
    def _migrate_schema():
        """Add new columns to existing tables if they don't exist"""
        import sqlite3

        try:
            # Use raw sqlite3 connection for schema migration
            conn = sqlite3.connect(sqlite_file_name)
            cursor = conn.cursor()

            # Get existing columns
            cursor.execute("PRAGMA table_info(minimadoc)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # Add indexing_time_seconds column if it doesn't exist
            if 'indexing_time_seconds' not in existing_columns:
                logger.info("Adding indexing_time_seconds column to minimadoc table")
                cursor.execute("ALTER TABLE minimadoc ADD COLUMN indexing_time_seconds FLOAT")
                conn.commit()

            # Add status column if it doesn't exist
            if 'status' not in existing_columns:
                logger.info("Adding status column to minimadoc table")
                cursor.execute(f"ALTER TABLE minimadoc ADD COLUMN status VARCHAR DEFAULT '{FileStatus.uploaded}'")
                conn.commit()

            conn.close()
            logger.info("Database schema migration completed successfully")
        except Exception as e:
            logger.error(f"Error during schema migration: {e}")
            logger.error("You may need to manually update the database or delete it to recreate with new schema")

    @staticmethod
    def delete_m_doc(fpath: str) -> None:
        with Session(engine) as session:
            statement = select(MinimaDoc).where(MinimaDoc.fpath == fpath)
            results = session.exec(statement)
            doc = results.one()
            session.delete(doc)
            session.commit()
            print("doc deleted:", doc)

    @staticmethod
    def select_m_doc(fpath: str) -> MinimaDoc:
        with Session(engine) as session:
            statement = select(MinimaDoc).where(MinimaDoc.fpath == fpath)
            results = session.exec(statement)
            doc = results.one()
            print("doc:", doc)
            return doc

    @staticmethod
    def find_removed_files(existing_file_paths: set[str]):
        removed_files: list[str] = []
        with Session(engine) as session:
            statement = select(MinimaDoc)
            results = session.exec(statement)
            logger.debug(f"find_removed_files count found {results}")
            for doc in results:
                logger.debug(f"find_removed_files file {doc.fpath} checking to remove")
                if doc.fpath not in existing_file_paths:
                    logger.debug(f"find_removed_files file {doc.fpath} does not exist anymore, removing")
                    removed_files.append(doc.fpath)
        for fpath in removed_files:
            MinimaStore.delete_m_doc(fpath)
        return removed_files

    @staticmethod
    def check_needs_indexing(fpath: str, last_updated_seconds: int) -> IndexingStatus:
        indexing_status: IndexingStatus = IndexingStatus.no_need_reindexing
        try:
            with Session(engine) as session:
                statement = select(MinimaDoc).where(MinimaDoc.fpath == fpath)
                results = session.exec(statement)
                doc = results.first()
                if doc is not None:
                    logger.debug(
                        f"file {fpath} new last updated={last_updated_seconds} old last updated: {doc.last_updated_seconds}"
                    )
                    if doc.last_updated_seconds < last_updated_seconds:
                        indexing_status = IndexingStatus.need_reindexing
                        logger.debug(f"file {fpath} needs indexing, timestamp changed")
                        doc_update = MinimaDocUpdate(fpath=fpath, last_updated_seconds=last_updated_seconds)
                        doc_data = doc_update.model_dump(exclude_unset=True)
                        doc.sqlmodel_update(doc_data)
                        session.add(doc)
                        session.commit()
                    else:
                        logger.debug(f"file {fpath} doesn't need indexing, timestamp same")
                else:
                    doc = MinimaDoc(fpath=fpath, last_updated_seconds=last_updated_seconds)
                    session.add(doc)
                    session.commit()
                    logger.debug(f"file {fpath} needs indexing, new file")
                    indexing_status = IndexingStatus.new_file
            return indexing_status
        except Exception as e:
            logger.error(f"error updating file in the store {e}, skipping indexing")
            return IndexingStatus.no_need_reindexing

    @staticmethod
    def update_indexing_time(fpath: str, indexing_time_seconds: float) -> None:
        try:
            with Session(engine) as session:
                statement = select(MinimaDoc).where(MinimaDoc.fpath == fpath)
                results = session.exec(statement)
                doc = results.first()
                if doc is not None:
                    doc_update = MinimaDocUpdate(indexing_time_seconds=indexing_time_seconds)
                    doc_data = doc_update.model_dump(exclude_unset=True)
                    doc.sqlmodel_update(doc_data)
                    session.add(doc)
                    session.commit()
                    logger.debug(f"Updated indexing time for {fpath}: {indexing_time_seconds}s")
        except Exception as e:
            logger.error(f"Error updating indexing time for {fpath}: {e}")

    @staticmethod
    def get_all_docs() -> list[MinimaDoc]:
        with Session(engine) as session:
            statement = select(MinimaDoc)
            results = session.exec(statement)
            return list(results.all())

    @staticmethod
    def get_indexing_stats() -> dict:
        docs = MinimaStore.get_all_docs()
        if not docs:
            return {
                "total_files": 0,
                "total_indexing_time": 0.0,
                "average_indexing_time": 0.0,
                "files": []
            }

        total_time = sum(doc.indexing_time_seconds or 0.0 for doc in docs)
        files_with_time = [doc for doc in docs if doc.indexing_time_seconds is not None]
        avg_time = total_time / len(files_with_time) if files_with_time else 0.0

        return {
            "total_files": len(docs),
            "total_indexing_time": round(total_time, 2),
            "average_indexing_time": round(avg_time, 2),
            "files": [
                {
                    "path": doc.fpath,
                    "indexing_time_seconds": round(doc.indexing_time_seconds, 2) if doc.indexing_time_seconds else None,
                    "last_updated": doc.last_updated_seconds,
                    "status": doc.status
                }
                for doc in docs
            ]
        }

    @staticmethod
    def update_file_status(fpath: str, status: FileStatus) -> None:
        try:
            with Session(engine) as session:
                statement = select(MinimaDoc).where(MinimaDoc.fpath == fpath)
                results = session.exec(statement)
                doc = results.first()
                if doc is not None:
                    doc_update = MinimaDocUpdate(status=status)
                    doc_data = doc_update.model_dump(exclude_unset=True)
                    doc.sqlmodel_update(doc_data)
                    session.add(doc)
                    session.commit()
                    logger.debug(f"Updated status for {fpath}: {status}")
        except Exception as e:
            logger.error(f"Error updating status for {fpath}: {e}")

    @staticmethod
    def get_files_status(fpaths: list[str]) -> list[dict]:
        with Session(engine) as session:
            statement = select(MinimaDoc).where(MinimaDoc.fpath.in_(fpaths))
            results = session.exec(statement)
            docs = results.all()
            return [
                {
                    "path": doc.fpath,
                    "status": doc.status,
                    "indexing_time_seconds": round(doc.indexing_time_seconds, 2) if doc.indexing_time_seconds else None,
                    "last_updated": doc.last_updated_seconds
                }
                for doc in docs
            ]
