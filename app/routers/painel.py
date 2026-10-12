from datetime import date

from fastapi import APIRouter, Depends
from sqlmodel import col, select

from app.db import SessionDep
from app.eventos_publicos import obter_eventos
from app.models import Reserva, agora
from app.schemas import PainelResposta, PendenciaPainel
from app.security import conferir_origem, usuario_atual
from app.services.apresentacao import montar_reservas, resumo_eventos

router = APIRouter(
    prefix="/api/painel",
    tags=["Painel"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)

DIAS_PARA_AVISAR_SEM_VAN = 45


@router.get("")
def resumo_do_painel(session: SessionDep) -> PainelResposta:
    """Visão geral das viagens que ainda vão acontecer: ocupação, dinheiro a receber e alertas."""
    hoje = date.today()
    eventos = sorted(
        (e for e in obter_eventos() if e.ativo and (e.data_fim is None or e.data_fim >= hoje)),
        key=lambda e: (e.data_inicio is None, e.data_inicio or date.max, e.id),
    )
    resumos, _ = resumo_eventos(session, eventos)
    titulos = {e.id: e.titulo for e in eventos}

    sem_veiculo = [
        r
        for r in resumos
        if r.veiculos == 0
        and r.data_inicio is not None
        and (r.data_inicio - hoje).days <= DIAS_PARA_AVISAR_SEM_VAN
    ]

    confirmadas = session.exec(
        select(Reserva).where(
            col(Reserva.evento_id).in_(list(titulos) or [0]), Reserva.situacao == "confirmado"
        )
    ).all()
    ordem_evento = {e.id: i for i, e in enumerate(eventos)}
    pendencias = [
        PendenciaPainel(
            reserva_id=r.id,
            veiculo_id=r.veiculo_id,
            passageiro=r.passageiro.nome,
            evento_titulo=titulos.get(r.evento_id),
            saldo_centavos=r.saldo_centavos,
            status_pagamento=r.status_pagamento,
        )
        for r in sorted(
            montar_reservas(session, list(confirmadas)),
            key=lambda r: (ordem_evento.get(r.evento_id, 999), -r.saldo_centavos),
        )
        if r.saldo_centavos > 0
    ]

    return PainelResposta(
        gerado_em=agora(),
        proximas_viagens=len(eventos),
        assentos=sum(r.assentos for r in resumos),
        confirmados=sum(r.confirmados for r in resumos),
        em_espera=sum(r.em_espera for r in resumos),
        pago_centavos=sum(r.pago_centavos for r in resumos),
        a_receber_centavos=sum(r.a_receber_centavos for r in resumos),
        sem_veiculo=sem_veiculo,
        proximos=resumos[:8],
        pendencias=pendencias[:15],
    )
