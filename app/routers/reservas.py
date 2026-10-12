from fastapi import APIRouter, Depends, HTTPException, status

from app.db import SessionDep
from app.models import Pagamento, Reserva
from app.schemas import (
    PagamentoEntrada,
    QuitacaoEntrada,
    ReservaAtualizacao,
    ReservaPublica,
    TransferenciaEntrada,
)
from app.security import UsuarioAtual, conferir_origem, usuario_atual
from app.services import reservas as regras
from app.services.apresentacao import montar_reservas

router = APIRouter(
    prefix="/api",
    tags=["Reservas e pagamentos"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _reserva_ou_404(session: SessionDep, reserva_id: int) -> Reserva:
    reserva = session.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada.")
    return reserva


def _resposta(session: SessionDep, reserva: Reserva) -> ReservaPublica:
    session.commit()
    session.refresh(reserva)
    return montar_reservas(session, [reserva])[0]


@router.patch("/reservas/{reserva_id}")
def atualizar_reserva(reserva_id: int, dados: ReservaAtualizacao, session: SessionDep) -> ReservaPublica:
    reserva = regras.atualizar_reserva(session, _reserva_ou_404(session, reserva_id), dados)
    return _resposta(session, reserva)


@router.post("/reservas/{reserva_id}/espera")
def mandar_para_espera(reserva_id: int, session: SessionDep) -> ReservaPublica:
    reserva = regras.mover_para_espera(session, _reserva_ou_404(session, reserva_id))
    return _resposta(session, reserva)


@router.post("/reservas/{reserva_id}/confirmar")
def confirmar_da_espera(reserva_id: int, session: SessionDep) -> ReservaPublica:
    reserva = regras.promover(session, _reserva_ou_404(session, reserva_id))
    return _resposta(session, reserva)


@router.post("/reservas/{reserva_id}/cancelar")
def cancelar_reserva(reserva_id: int, session: SessionDep) -> ReservaPublica:
    reserva = regras.cancelar(session, _reserva_ou_404(session, reserva_id))
    return _resposta(session, reserva)


@router.post("/reservas/{reserva_id}/transferir")
def transferir_reserva(reserva_id: int, dados: TransferenciaEntrada, session: SessionDep) -> ReservaPublica:
    reserva = regras.transferir(
        session,
        _reserva_ou_404(session, reserva_id),
        dados.veiculo_id,
        dados.entrar_na_espera_se_lotado,
    )
    return _resposta(session, reserva)


@router.delete("/reservas/{reserva_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_reserva(reserva_id: int, session: SessionDep) -> None:
    regras.apagar_reserva(session, _reserva_ou_404(session, reserva_id))
    session.commit()


@router.post("/reservas/{reserva_id}/pagamentos", status_code=status.HTTP_201_CREATED)
def registrar_pagamento(
    reserva_id: int, dados: PagamentoEntrada, usuario: UsuarioAtual, session: SessionDep
) -> ReservaPublica:
    """Registra um pagamento (parcial ou o que fecha a conta). O status é calculado."""
    reserva = _reserva_ou_404(session, reserva_id)
    regras.registrar_pagamento(session, reserva, dados, usuario.nome)
    return _resposta(session, reserva)


@router.post("/reservas/{reserva_id}/quitar", status_code=status.HTTP_201_CREATED)
def quitar_reserva(
    reserva_id: int, dados: QuitacaoEntrada, usuario: UsuarioAtual, session: SessionDep
) -> ReservaPublica:
    """Marca como pago por completo: registra o que falta, na data informada (ou hoje)."""
    reserva = _reserva_ou_404(session, reserva_id)
    regras.quitar(session, reserva, dados, usuario.nome)
    return _resposta(session, reserva)


@router.delete("/pagamentos/{pagamento_id}")
def desfazer_pagamento(pagamento_id: int, session: SessionDep) -> ReservaPublica:
    """Para corrigir um lançamento errado. O pagamento some e o status é recalculado."""
    pagamento = session.get(Pagamento, pagamento_id)
    if pagamento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pagamento não encontrado.")
    reserva = _reserva_ou_404(session, pagamento.reserva_id)
    session.delete(pagamento)
    session.flush()
    return _resposta(session, reserva)
