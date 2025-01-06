import logging
from sqlmodel import Field, Session, SQLModel, create_engine, select

from singleton import Singleton
from enum import Enum

logger = logging.getLogger(__name__)


class IndexingStatus(Enum):
    new_file = 1
    need_reindexing = 2
    no_need_reindexing = 3


class MinimaDoc(SQLModel, table=True):
    fpath: str = Field(primary_key=True)
    last_updated_seconds: int | None = Field(default=None, index=True)


class MinimaDocUpdate(SQLModel):
    fpath: str | None = None
    last_updated_seconds: int | None = None


sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

connect_args = {"check_same_thread": False}
engine = create_engine(sqlite_url, connect_args=connect_args)


class MinimaStore(metaclass=Singleton):

    @staticmethod
    def create_db_and_tables():
        SQLModel.metadata.create_all(engine)

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
            logger.info(f"find_removed_files count found {results}")
            for doc in results:
                logger.info(f"find_removed_files file {doc.fpath} checking to remove")
                if doc.fpath not in existing_file_paths:
                    logger.info(f"find_removed_files file {doc.fpath} does not exist anymore, removing")
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
                    logger.info(
                        f"file {fpath} new last updated={last_updated_seconds} old last updated: {doc.last_updated_seconds}"
                    )
                    if doc.last_updated_seconds < last_updated_seconds:
                        indexing_status = IndexingStatus.need_reindexing
                        logger.info(f"file {fpath} needs indexing, timestamp changed")
                        doc_update = MinimaDocUpdate(fpath=fpath, last_updated_seconds=last_updated_seconds)
                        doc_data = doc_update.model_dump(exclude_unset=True)
                        doc.sqlmodel_update(doc_data)
                        session.add(doc)
                        session.commit()
                    else:
                        logger.info(f"file {fpath} doesn't need indexing, timestamp same")
                else:
                    doc = MinimaDoc(fpath=fpath, last_updated_seconds=last_updated_seconds)
                    session.add(doc)
                    session.commit()
                    logger.info(f"file {fpath} needs indexing, new file")
                    indexing_status = IndexingStatus.new_file
            return indexing_status
        except Exception as e:
            logger.error(f"error updating file in the store {e}, skipping indexing")
            return IndexingStatus.no_need_reindexing
