from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, func, or_, select

from app.db import SessionDep
from app.models import Contato, Veiculo, agora
from app.schemas import CategoriaContato, ContatoAtualizacao, ContatoEntrada, ContatoPublico
from app.security import conferir_origem, usuario_atual
from app.services.apresentacao import contato_publico
from app.services.reservas import RegraDeNegocio

router = APIRouter(
    prefix="/api/contatos",
    tags=["Contatos"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _contato_ou_404(session: SessionDep, contato_id: int) -> Contato:
    contato = session.get(Contato, contato_id)
    if contato is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contato não encontrado.")
    return contato


def _veiculos_por_contato(session: SessionDep) -> dict[int, int]:
    return dict(
        session.exec(
            select(Veiculo.contato_id, func.count())
            .where(col(Veiculo.contato_id).is_not(None))
            .group_by(Veiculo.contato_id)
        ).all()
    )


@router.get("")
def listar_contatos(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=80)] = None,
    categoria: CategoriaContato | None = None,
    somente_ativos: bool = False,
) -> list[ContatoPublico]:
    consulta = select(Contato)
    if categoria:
        consulta = consulta.where(Contato.categoria == categoria)
    if somente_ativos:
        consulta = consulta.where(Contato.ativo)
    if q and q.strip():
        termo = f"%{q.strip()}%"
        consulta = consulta.where(
            or_(
                col(Contato.nome).ilike(termo),
                col(Contato.empresa).ilike(termo),
                col(Contato.telefone).ilike(termo),
                col(Contato.email).ilike(termo),
            )
        )
    contatos = session.exec(consulta.order_by(func.lower(Contato.nome))).all()
    uso = _veiculos_por_contato(session)
    return [contato_publico(c, uso.get(c.id, 0)) for c in contatos]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_contato(dados: ContatoEntrada, session: SessionDep) -> ContatoPublico:
    contato = Contato(**dados.model_dump())
    session.add(contato)
    session.commit()
    session.refresh(contato)
    return contato_publico(contato)


@router.get("/{contato_id}")
def obter_contato(contato_id: int, session: SessionDep) -> ContatoPublico:
    contato = _contato_ou_404(session, contato_id)
    return contato_publico(contato, _veiculos_por_contato(session).get(contato.id, 0))


@router.patch("/{contato_id}")
def editar_contato(contato_id: int, dados: ContatoAtualizacao, session: SessionDep) -> ContatoPublico:
    contato = _contato_ou_404(session, contato_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        if valor is not None or campo in {"empresa", "telefone", "email", "observacoes"}:
            setattr(contato, campo, valor)
    contato.atualizado_em = agora()
    session.add(contato)
    session.commit()
    session.refresh(contato)
    return contato_publico(contato, _veiculos_por_contato(session).get(contato.id, 0))


@router.delete("/{contato_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_contato(contato_id: int, session: SessionDep) -> None:
    contato = _contato_ou_404(session, contato_id)
    uso = _veiculos_por_contato(session).get(contato.id, 0)
    if uso:
        raise RegraDeNegocio(
            f"Este contato está ligado a {uso} {'van' if uso == 1 else 'vans'}. Desative em vez de apagar."
        )
    session.delete(contato)
    session.commit()
