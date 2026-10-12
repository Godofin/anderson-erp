from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings


def normalizar_url(url: str) -> str:
    """O Neon entrega postgres:// ou postgresql://; o SQLAlchemy 2 usa o driver psycopg 3."""
    for prefixo in ("postgres://", "postgresql://"):
        if url.startswith(prefixo):
            return "postgresql+psycopg://" + url[len(prefixo) :]
    return url


def criar_engine(url: str) -> Engine:
    url = normalizar_url(url)
    if url.startswith("sqlite"):
        engine = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _ativar_chaves_estrangeiras(conexao, _registro):  # pragma: no cover
            cursor = conexao.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine
    # Na Vercel cada instância abre as suas conexões: poucas e renovadas, para não esgotar o Neon
    return create_engine(url, pool_pre_ping=True, pool_size=2, max_overflow=3, pool_recycle=300)


engine = criar_engine(get_settings().database_url)


def criar_tabelas() -> None:
    """Cria só as tabelas erp_*. As tabelas da API pública não fazem parte deste metadata."""
    import app.models  # noqa: F401  (registra as tabelas no metadata)

    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
