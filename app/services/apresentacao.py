"""Monta as respostas da API a partir das tabelas, com poucas consultas (nada de N+1)."""

from collections import defaultdict

from sqlmodel import Session, col, func, select

from app.eventos_publicos import EventoPublico
from app.models import Contato, Fechamento, Pagamento, Passageiro, Reserva, Veiculo
from app.schemas import (
    ContatoMini,
    ContatoPublico,
    EventoResumo,
    PagamentoPublico,
    PassageiroResumo,
    ReservaPublica,
    VeiculoDetalhe,
    VeiculoResumo,
)
from app.services.documentos import mascarar_documento
from app.services.reservas import status_pagamento


def passageiro_resumo(p: Passageiro) -> PassageiroResumo:
    return PassageiroResumo(
        id=p.id,
        nome=p.nome,
        documento_tipo=p.documento_tipo,  # type: ignore[arg-type]
        documento_mascarado=mascarar_documento(p.documento_tipo, p.documento_numero),
    )


def _pagamentos_por_reserva(session: Session, reserva_ids: list[int]) -> dict[int, list[Pagamento]]:
    if not reserva_ids:
        return {}
    linhas = session.exec(
        select(Pagamento)
        .where(col(Pagamento.reserva_id).in_(reserva_ids))
        .order_by(col(Pagamento.data), col(Pagamento.id))
    ).all()
    agrupado: dict[int, list[Pagamento]] = defaultdict(list)
    for pagamento in linhas:
        agrupado[pagamento.reserva_id].append(pagamento)
    return agrupado


def _posicoes_de_espera(session: Session, veiculo_ids: set[int]) -> dict[int, int]:
    """Posição de cada reserva na fila da sua van: quem entrou primeiro é o 1."""
    if not veiculo_ids:
        return {}
    na_espera = session.exec(
        select(Reserva)
        .where(col(Reserva.veiculo_id).in_(veiculo_ids), Reserva.situacao == "espera")
        .order_by(col(Reserva.entrou_na_espera_em), col(Reserva.id))
    ).all()
    contador: dict[int, int] = defaultdict(int)
    posicoes: dict[int, int] = {}
    for reserva in na_espera:
        contador[reserva.veiculo_id] += 1
        posicoes[reserva.id] = contador[reserva.veiculo_id]
    return posicoes


def montar_reservas(session: Session, reservas: list[Reserva]) -> list[ReservaPublica]:
    if not reservas:
        return []
    passageiros = {
        p.id: p
        for p in session.exec(
            select(Passageiro).where(col(Passageiro.id).in_({r.passageiro_id for r in reservas}))
        ).all()
    }
    pagamentos = _pagamentos_por_reserva(session, [r.id for r in reservas])
    posicoes = _posicoes_de_espera(session, {r.veiculo_id for r in reservas})

    saida: list[ReservaPublica] = []
    for r in reservas:
        lista = pagamentos.get(r.id, [])
        pago = sum(p.valor_centavos for p in lista)
        saida.append(
            ReservaPublica(
                id=r.id,
                veiculo_id=r.veiculo_id,
                evento_id=r.evento_id,
                passageiro=passageiro_resumo(passageiros[r.passageiro_id]),
                situacao=r.situacao,  # type: ignore[arg-type]
                assento=r.assento,
                posicao_espera=posicoes.get(r.id),
                cidade_embarque=r.cidade_embarque,
                valor_total_centavos=r.valor_total_centavos,
                pago_centavos=pago,
                saldo_centavos=max(r.valor_total_centavos - pago, 0),
                status_pagamento=status_pagamento(r.valor_total_centavos, pago),  # type: ignore[arg-type]
                ultimo_pagamento=lista[-1].data if lista else None,
                observacoes=r.observacoes,
                pagamentos=[
                    PagamentoPublico(
                        id=p.id,
                        data=p.data,
                        valor_centavos=p.valor_centavos,
                        tipo=p.tipo,  # type: ignore[arg-type]
                        observacao=p.observacao,
                        registrado_por=p.registrado_por,
                    )
                    for p in lista
                ],
            )
        )
    return saida


def resumo_veiculos(session: Session, veiculos: list[Veiculo]) -> list[VeiculoResumo]:
    if not veiculos:
        return []
    ids = [v.id for v in veiculos]
    reservas = session.exec(select(Reserva).where(col(Reserva.veiculo_id).in_(ids))).all()
    pago_por_reserva = dict(
        session.exec(
            select(Pagamento.reserva_id, func.sum(Pagamento.valor_centavos))
            .where(col(Pagamento.reserva_id).in_([r.id for r in reservas] or [0]))
            .group_by(Pagamento.reserva_id)
        ).all()
    )
    contatos = {
        c.id: c
        for c in session.exec(
            select(Contato).where(
                col(Contato.id).in_([v.contato_id for v in veiculos if v.contato_id] or [0])
            )
        ).all()
    }

    fechamentos = {
        f.veiculo_id: f
        for f in session.exec(select(Fechamento).where(col(Fechamento.veiculo_id).in_(ids))).all()
    }

    por_veiculo: dict[int, list[Reserva]] = defaultdict(list)
    for r in reservas:
        por_veiculo[r.veiculo_id].append(r)

    saida: list[VeiculoResumo] = []
    for v in veiculos:
        suas = por_veiculo.get(v.id, [])
        confirmadas = [r for r in suas if r.situacao == "confirmado"]
        recebido = sum(int(pago_por_reserva.get(r.id, 0)) for r in suas)
        a_receber = sum(
            max(r.valor_total_centavos - int(pago_por_reserva.get(r.id, 0)), 0) for r in confirmadas
        )
        contato = contatos.get(v.contato_id) if v.contato_id else None
        saida.append(
            VeiculoResumo(
                id=v.id,
                evento_id=v.evento_id,
                nome=v.nome,
                tipo=v.tipo,  # type: ignore[arg-type]
                placa=v.placa,
                capacidade=v.capacidade,
                confirmados=len(confirmadas),
                livres=max(v.capacidade - len(confirmadas), 0),
                em_espera=sum(1 for r in suas if r.situacao == "espera"),
                fechada=v.id in fechamentos,
                fechada_em=fechamentos[v.id].fechada_em if v.id in fechamentos else None,
                pago_centavos=recebido,
                a_receber_centavos=a_receber,
                contato=(
                    ContatoMini(
                        id=contato.id,
                        nome=contato.nome,
                        telefone=contato.telefone,
                        categoria=contato.categoria,  # type: ignore[arg-type]
                    )
                    if contato
                    else None
                ),
            )
        )
    return saida


def resumo_eventos(
    session: Session, eventos: list[EventoPublico]
) -> tuple[list[EventoResumo], dict[int, list[VeiculoResumo]]]:
    """Resumo de cada evento (com os totais das vans) e as vans de cada um."""
    if not eventos:
        return [], {}
    veiculos = session.exec(
        select(Veiculo).where(col(Veiculo.evento_id).in_([e.id for e in eventos])).order_by(col(Veiculo.id))
    ).all()
    resumos = resumo_veiculos(session, list(veiculos))
    por_evento: dict[int, list[VeiculoResumo]] = defaultdict(list)
    for resumo in resumos:
        por_evento[resumo.evento_id].append(resumo)

    saida = [
        EventoResumo(
            id=e.id,
            titulo=e.titulo,
            data_texto=e.data_texto,
            data_inicio=e.data_inicio,
            data_fim=e.data_fim,
            imagem=e.imagem,
            ativo=e.ativo,
            destaque=e.destaque,
            tipo=e.tipo,  # type: ignore[arg-type]
            cidades=e.cidades,
            veiculos=len(por_evento.get(e.id, [])),
            assentos=sum(v.capacidade for v in por_evento.get(e.id, [])),
            confirmados=sum(v.confirmados for v in por_evento.get(e.id, [])),
            em_espera=sum(v.em_espera for v in por_evento.get(e.id, [])),
            pago_centavos=sum(v.pago_centavos for v in por_evento.get(e.id, [])),
            a_receber_centavos=sum(v.a_receber_centavos for v in por_evento.get(e.id, [])),
        )
        for e in eventos
    ]
    return saida, por_evento


def contato_publico(c: Contato, veiculos: int = 0) -> ContatoPublico:
    return ContatoPublico(
        id=c.id,
        nome=c.nome,
        categoria=c.categoria,  # type: ignore[arg-type]
        empresa=c.empresa,
        telefone=c.telefone,
        email=c.email,
        observacoes=c.observacoes,
        ativo=c.ativo,
        veiculos=veiculos,
    )


def detalhe_veiculo(session: Session, veiculo: Veiculo) -> VeiculoDetalhe:
    resumo = resumo_veiculos(session, [veiculo])[0]
    reservas = session.exec(
        select(Reserva).where(Reserva.veiculo_id == veiculo.id).order_by(col(Reserva.id))
    ).all()
    publicas = montar_reservas(session, list(reservas))
    return VeiculoDetalhe(
        **resumo.model_dump(),
        valor_padrao_centavos=veiculo.valor_padrao_centavos,
        observacoes=veiculo.observacoes,
        confirmadas=sorted((r for r in publicas if r.situacao == "confirmado"), key=lambda r: r.assento or 0),
        espera=sorted((r for r in publicas if r.situacao == "espera"), key=lambda r: r.posicao_espera or 0),
        canceladas=[r for r in publicas if r.situacao == "cancelado"],
    )
