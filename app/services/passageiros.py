"""Cadastro de passageiros: criação e edição com documento único."""

from fastapi import HTTPException, status
from sqlmodel import Session, select

from app.models import Passageiro, agora
from app.schemas import PassageiroAtualizacao, PassageiroEntrada


def buscar_por_documento(session: Session, tipo: str, numero: str) -> Passageiro | None:
    return session.exec(
        select(Passageiro).where(Passageiro.documento_tipo == tipo, Passageiro.documento_numero == numero)
    ).first()


def _conflito(existente: Passageiro) -> HTTPException:
    return HTTPException(
        status.HTTP_409_CONFLICT,
        {
            "mensagem": f"Esse documento já está cadastrado para {existente.nome}.",
            "passageiro_id": existente.id,
        },
    )


def criar_passageiro(session: Session, dados: PassageiroEntrada) -> Passageiro:
    existente = buscar_por_documento(session, dados.documento_tipo, dados.documento_numero)
    if existente:
        raise _conflito(existente)
    passageiro = Passageiro(**dados.model_dump())
    session.add(passageiro)
    session.flush()
    return passageiro


def atualizar_passageiro(
    session: Session, passageiro: Passageiro, dados: PassageiroAtualizacao
) -> Passageiro:
    mudancas = dados.model_dump(exclude_unset=True)
    if "documento_tipo" in mudancas:
        outro = buscar_por_documento(session, mudancas["documento_tipo"], mudancas["documento_numero"])
        if outro and outro.id != passageiro.id:
            raise _conflito(outro)
    for campo, valor in mudancas.items():
        setattr(passageiro, campo, valor)
    passageiro.atualizado_em = agora()
    session.add(passageiro)
    session.flush()
    return passageiro
