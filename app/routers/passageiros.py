from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import col, func, or_, select

from app.api_publica import ApiPublicaIndisponivel
from app.db import SessionDep
from app.eventos_publicos import obter_eventos
from app.models import Passageiro, Reserva, Veiculo, agora
from app.schemas import (
    HistoricoViagem,
    PassageiroAtualizacao,
    PassageiroDetalhe,
    PassageiroEntrada,
    PassageiroLinha,
)
from app.security import conferir_origem, usuario_atual
from app.services.apresentacao import _pagamentos_por_reserva, passageiro_resumo
from app.services.documentos import formatar_documento, normalizar_rg
from app.services.passageiros import atualizar_passageiro, criar_passageiro
from app.services.reservas import RegraDeNegocio, status_pagamento

router = APIRouter(
    prefix="/api/passageiros",
    tags=["Passageiros"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _passageiro_ou_404(session: SessionDep, passageiro_id: int) -> Passageiro:
    passageiro = session.get(Passageiro, passageiro_id)
    if passageiro is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Passageiro não encontrado.")
    return passageiro


def _detalhe(session: SessionDep, passageiro: Passageiro) -> PassageiroDetalhe:
    reservas = session.exec(
        select(Reserva).where(Reserva.passageiro_id == passageiro.id).order_by(col(Reserva.id).desc())
    ).all()
    veiculos = {
        v.id: v
        for v in session.exec(
            select(Veiculo).where(col(Veiculo.id).in_([r.veiculo_id for r in reservas] or [0]))
        ).all()
    }
    pagamentos = _pagamentos_por_reserva(session, [r.id for r in reservas])
    try:
        titulos = {e.id: e.titulo for e in obter_eventos()}
    except ApiPublicaIndisponivel:
        titulos = {}
    viagens = []
    for r in reservas:
        pago = sum(p.valor_centavos for p in pagamentos.get(r.id, []))
        viagens.append(
            HistoricoViagem(
                reserva_id=r.id,
                evento_id=r.evento_id,
                evento_titulo=titulos.get(r.evento_id),
                veiculo_id=r.veiculo_id,
                veiculo_nome=veiculos[r.veiculo_id].nome,
                situacao=r.situacao,  # type: ignore[arg-type]
                status_pagamento=status_pagamento(r.valor_total_centavos, pago),  # type: ignore[arg-type]
                saldo_centavos=max(r.valor_total_centavos - pago, 0),
            )
        )
    return PassageiroDetalhe(
        **passageiro_resumo(passageiro).model_dump(),
        documento_numero=passageiro.documento_numero,
        documento_formatado=formatar_documento(passageiro.documento_tipo, passageiro.documento_numero),
        viagens=viagens,
    )


@router.get("")
def listar_passageiros(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=80)] = None,
    limite: Annotated[int, Query(ge=1, le=300)] = 200,
) -> list[PassageiroLinha]:
    """Busca por nome ou por parte do documento. Na lista o documento aparece mascarado."""
    consulta = select(Passageiro)
    if q and q.strip():
        termo = q.strip()
        filtros = [col(Passageiro.nome).ilike(f"%{termo}%")]
        documento = normalizar_rg(termo)
        if len(documento) >= 3:
            filtros.append(col(Passageiro.documento_numero).contains(documento))
        consulta = consulta.where(or_(*filtros))
    passageiros = session.exec(consulta.order_by(func.lower(Passageiro.nome)).limit(limite)).all()
    contagem = dict(
        session.exec(
            select(Reserva.passageiro_id, func.count())
            .where(
                col(Reserva.passageiro_id).in_([p.id for p in passageiros] or [0]),
                Reserva.situacao != "cancelado",
            )
            .group_by(Reserva.passageiro_id)
        ).all()
    )
    return [
        PassageiroLinha(**passageiro_resumo(p).model_dump(), viagens=int(contagem.get(p.id, 0)))
        for p in passageiros
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def cadastrar_passageiro(dados: PassageiroEntrada, session: SessionDep) -> PassageiroDetalhe:
    passageiro = criar_passageiro(session, dados)
    session.commit()
    session.refresh(passageiro)
    return _detalhe(session, passageiro)


@router.get("/{passageiro_id}")
def obter_passageiro(passageiro_id: int, session: SessionDep) -> PassageiroDetalhe:
    return _detalhe(session, _passageiro_ou_404(session, passageiro_id))


@router.patch("/{passageiro_id}")
def editar_passageiro(
    passageiro_id: int, dados: PassageiroAtualizacao, session: SessionDep
) -> PassageiroDetalhe:
    passageiro = atualizar_passageiro(session, _passageiro_ou_404(session, passageiro_id), dados)
    passageiro.atualizado_em = agora()
    session.commit()
    session.refresh(passageiro)
    return _detalhe(session, passageiro)


@router.delete("/{passageiro_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_passageiro(passageiro_id: int, session: SessionDep) -> None:
    passageiro = _passageiro_ou_404(session, passageiro_id)
    total = session.exec(select(func.count()).where(Reserva.passageiro_id == passageiro.id)).one()
    if total:
        raise RegraDeNegocio(
            "Este passageiro tem viagens registradas e não pode ser apagado. Cancele as reservas dele."
        )
    session.delete(passageiro)
    session.commit()
