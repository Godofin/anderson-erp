"""Regras do dia a dia: lotação, lista de espera, troca de van e pagamentos.

Toda a lógica que decide "cabe ou vai para a espera" e "está pago ou parcial" fica aqui,
longe das rotas, para ser testada sem HTTP.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, func, select

from app.models import Fechamento, Pagamento, Passageiro, Reserva, Veiculo, agora
from app.schemas import (
    PagamentoEntrada,
    QuitacaoEntrada,
    ReservaAtualizacao,
    ReservaEntrada,
)
from app.services.passageiros import criar_passageiro


class RegraDeNegocio(HTTPException):
    """Erro que o usuário consegue resolver (409). A mensagem já vem pronta para a tela."""

    def __init__(self, mensagem: str, codigo: int = status.HTTP_409_CONFLICT) -> None:
        super().__init__(codigo, mensagem)


def reais(centavos: int) -> str:
    texto = f"{centavos / 100:,.2f}"
    return "R$ " + texto.replace(",", "#").replace(".", ",").replace("#", ".")


# ------------------------------------------------------------------ pagamento
def status_pagamento(total_centavos: int, pago_centavos: int) -> str:
    if total_centavos <= 0 and pago_centavos <= 0:
        return "sem_valor"
    if pago_centavos <= 0:
        return "pendente"
    if pago_centavos < total_centavos:
        return "parcial"
    return "pago"


def total_pago(session: Session, reserva_id: int) -> int:
    soma = session.exec(
        select(func.coalesce(func.sum(Pagamento.valor_centavos), 0)).where(Pagamento.reserva_id == reserva_id)
    ).one()
    return int(soma)


# ------------------------------------------------------------------ assentos
def bloquear_veiculo(session: Session, veiculo_id: int) -> Veiculo:
    """Busca a van travando a linha (Postgres), para duas pessoas não pegarem o mesmo assento."""
    veiculo = session.exec(select(Veiculo).where(Veiculo.id == veiculo_id).with_for_update()).first()
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    return veiculo


def van_fechada(session: Session, veiculo_id: int) -> bool:
    return session.get(Fechamento, veiculo_id) is not None


def exigir_aberta(session: Session, veiculo_id: int) -> None:
    """A lista de uma van fechada não muda. Para mexer, é preciso reabrir."""
    if van_fechada(session, veiculo_id):
        raise RegraDeNegocio("Esta van está fechada. Reabra a van para mudar a lista de passageiros.")


def assentos_ocupados(session: Session, veiculo_id: int) -> dict[int, int]:
    linhas = session.exec(
        select(Reserva.assento, Reserva.id).where(
            Reserva.veiculo_id == veiculo_id,
            Reserva.situacao == "confirmado",
            Reserva.assento.is_not(None),  # type: ignore[union-attr]
        )
    ).all()
    return {assento: reserva_id for assento, reserva_id in linhas}


def contar_confirmados(session: Session, veiculo_id: int) -> int:
    return int(
        session.exec(
            select(func.count()).where(Reserva.veiculo_id == veiculo_id, Reserva.situacao == "confirmado")
        ).one()
    )


def primeiro_assento_livre(capacidade: int, ocupados: dict[int, int]) -> int | None:
    return next((n for n in range(1, capacidade + 1) if n not in ocupados), None)


def _validar_assento(
    veiculo: Veiculo, assento: int, ocupados: dict[int, int], ignorar: int | None = None
) -> None:
    if assento > veiculo.capacidade:
        raise RegraDeNegocio(f"Esta van só tem {veiculo.capacidade} assentos.")
    dono = ocupados.get(assento)
    if dono is not None and dono != ignorar:
        raise RegraDeNegocio(f"O assento {assento} já está ocupado.")


# ------------------------------------------------------------------ reservas
def adicionar_reserva(session: Session, veiculo_id: int, dados: ReservaEntrada) -> Reserva:
    veiculo = bloquear_veiculo(session, veiculo_id)
    exigir_aberta(session, veiculo.id)

    if dados.novo_passageiro is not None:
        passageiro = criar_passageiro(session, dados.novo_passageiro)
    else:
        passageiro = session.get(Passageiro, dados.passageiro_id)
        if passageiro is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Passageiro não encontrado.")

    existente = session.exec(
        select(Reserva).where(Reserva.evento_id == veiculo.evento_id, Reserva.passageiro_id == passageiro.id)
    ).first()
    if existente and existente.situacao != "cancelado":
        van = session.get(Veiculo, existente.veiculo_id)
        onde = f" ({van.nome})" if van else ""
        raise RegraDeNegocio(f"{passageiro.nome} já está nesta viagem{onde}.")

    ocupados = assentos_ocupados(session, veiculo.id)
    cheia = len(ocupados) >= veiculo.capacidade
    vai_para_espera = dados.lista_de_espera or cheia

    assento = None
    if not vai_para_espera:
        if dados.assento is not None:
            _validar_assento(veiculo, dados.assento, ocupados)
            assento = dados.assento
        else:
            assento = primeiro_assento_livre(veiculo.capacidade, ocupados)

    if dados.valor_total_centavos is not None:
        valor = dados.valor_total_centavos
    elif existente and existente.valor_total_centavos > 0:
        valor = existente.valor_total_centavos  # reativando: mantém o valor combinado
    else:
        valor = veiculo.valor_padrao_centavos

    reserva = existente or Reserva(
        veiculo_id=veiculo.id, evento_id=veiculo.evento_id, passageiro_id=passageiro.id, situacao=""
    )
    reserva.veiculo_id = veiculo.id
    reserva.situacao = "espera" if vai_para_espera else "confirmado"
    reserva.assento = assento
    reserva.entrou_na_espera_em = agora() if vai_para_espera else None
    reserva.cidade_embarque = dados.cidade_embarque or reserva.cidade_embarque
    reserva.valor_total_centavos = valor
    reserva.observacoes = dados.observacoes or reserva.observacoes
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def atualizar_reserva(session: Session, reserva: Reserva, dados: ReservaAtualizacao) -> Reserva:
    mudancas = dados.model_dump(exclude_unset=True)
    if reserva.situacao == "cancelado":
        raise RegraDeNegocio("Esta reserva está cancelada. Adicione o passageiro de novo para reativar.")

    if "assento" in mudancas and mudancas["assento"] is not None:
        if reserva.situacao != "confirmado":
            raise RegraDeNegocio("Só quem está confirmado tem assento.")
        veiculo = bloquear_veiculo(session, reserva.veiculo_id)
        exigir_aberta(session, veiculo.id)
        _validar_assento(
            veiculo, mudancas["assento"], assentos_ocupados(session, veiculo.id), ignorar=reserva.id
        )
    if "valor_total_centavos" in mudancas and mudancas["valor_total_centavos"] is not None:
        pago = total_pago(session, reserva.id)
        if mudancas["valor_total_centavos"] < pago:
            raise RegraDeNegocio(f"O valor total não pode ficar abaixo do que já foi pago ({reais(pago)}).")
    for campo, valor in mudancas.items():
        if valor is not None or campo in {"cidade_embarque", "observacoes"}:
            setattr(reserva, campo, valor)
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def mover_para_espera(session: Session, reserva: Reserva) -> Reserva:
    if reserva.situacao != "confirmado":
        raise RegraDeNegocio("Só dá para mandar para a lista de espera quem está confirmado.")
    exigir_aberta(session, reserva.veiculo_id)
    reserva.situacao = "espera"
    reserva.assento = None
    reserva.entrou_na_espera_em = agora()
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def promover(session: Session, reserva: Reserva) -> Reserva:
    if reserva.situacao != "espera":
        raise RegraDeNegocio("Só quem está na lista de espera pode ser confirmado.")
    veiculo = bloquear_veiculo(session, reserva.veiculo_id)
    exigir_aberta(session, veiculo.id)
    ocupados = assentos_ocupados(session, veiculo.id)
    assento = primeiro_assento_livre(veiculo.capacidade, ocupados)
    if assento is None:
        raise RegraDeNegocio("A van está lotada. Libere um assento antes de confirmar.")
    reserva.situacao = "confirmado"
    reserva.assento = assento
    reserva.entrou_na_espera_em = None
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def cancelar(session: Session, reserva: Reserva) -> Reserva:
    if reserva.situacao == "cancelado":
        raise RegraDeNegocio("Esta reserva já está cancelada.")
    if reserva.situacao == "confirmado":
        exigir_aberta(session, reserva.veiculo_id)
    reserva.situacao = "cancelado"
    reserva.assento = None
    reserva.entrou_na_espera_em = None
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def transferir(
    session: Session, reserva: Reserva, destino_id: int, entrar_na_espera_se_lotado: bool
) -> Reserva:
    if reserva.situacao == "cancelado":
        raise RegraDeNegocio("Reserva cancelada não pode ser transferida.")
    if destino_id == reserva.veiculo_id:
        raise RegraDeNegocio("O passageiro já está nesta van.")
    # trava as duas vans sempre na mesma ordem, para não travar uma na outra
    primeiro, segundo = sorted((reserva.veiculo_id, destino_id))
    bloquear_veiculo(session, primeiro)
    bloquear_veiculo(session, segundo)
    destino = session.get(Veiculo, destino_id)
    if destino.evento_id != reserva.evento_id:
        raise RegraDeNegocio("Só dá para transferir entre vans da mesma viagem.")
    if reserva.situacao == "confirmado":
        exigir_aberta(session, reserva.veiculo_id)
    exigir_aberta(session, destino.id)

    if reserva.situacao == "confirmado":
        ocupados = assentos_ocupados(session, destino.id)
        assento = primeiro_assento_livre(destino.capacidade, ocupados)
        if assento is None:
            if not entrar_na_espera_se_lotado:
                raise RegraDeNegocio(
                    f"{destino.nome} está lotada. Transfira para a lista de espera dela, se quiser."
                )
            reserva.situacao = "espera"
            reserva.entrou_na_espera_em = agora()
        reserva.assento = assento
    reserva.veiculo_id = destino.id
    reserva.atualizado_em = agora()
    session.add(reserva)
    session.flush()
    return reserva


def apagar_reserva(session: Session, reserva: Reserva) -> None:
    if reserva.situacao == "confirmado":
        exigir_aberta(session, reserva.veiculo_id)
    if total_pago(session, reserva.id) > 0:
        raise RegraDeNegocio(
            "Há pagamentos registrados nesta reserva. Cancele em vez de apagar, para manter o histórico."
        )
    session.delete(reserva)
    session.flush()


# ------------------------------------------------------------------ pagamentos
def _preparar_pagamento(session: Session, reserva: Reserva) -> tuple[int, int]:
    if reserva.situacao == "cancelado":
        raise RegraDeNegocio(
            "Esta reserva está cancelada. Reative o passageiro antes de registrar pagamento."
        )
    if reserva.valor_total_centavos <= 0:
        raise RegraDeNegocio("Defina o valor total da reserva antes de registrar pagamentos.", 422)
    pago = total_pago(session, reserva.id)
    return reserva.valor_total_centavos - pago, pago


def _validar_data(data: date | None) -> date:
    hoje = date.today()
    if data is None:
        return hoje
    if data > hoje:
        raise RegraDeNegocio("A data do pagamento não pode ser no futuro.", 422)
    return data


def registrar_pagamento(
    session: Session, reserva: Reserva, dados: PagamentoEntrada, usuario: str
) -> Pagamento:
    saldo, _ = _preparar_pagamento(session, reserva)
    if saldo <= 0:
        raise RegraDeNegocio("Esta reserva já está quitada.")
    if dados.valor_centavos > saldo:
        raise RegraDeNegocio(f"O valor passa do saldo, que é {reais(saldo)}.")
    pagamento = Pagamento(
        reserva_id=reserva.id,
        data=_validar_data(dados.data),
        valor_centavos=dados.valor_centavos,
        tipo="total" if dados.valor_centavos == saldo else "parcial",
        observacao=dados.observacao,
        registrado_por=usuario,
    )
    session.add(pagamento)
    session.flush()
    return pagamento


def quitar(session: Session, reserva: Reserva, dados: QuitacaoEntrada, usuario: str) -> Pagamento:
    saldo, _ = _preparar_pagamento(session, reserva)
    if saldo <= 0:
        raise RegraDeNegocio("Esta reserva já está quitada.")
    pagamento = Pagamento(
        reserva_id=reserva.id,
        data=_validar_data(dados.data),
        valor_centavos=saldo,
        tipo="total",
        observacao=dados.observacao,
        registrado_por=usuario,
    )
    session.add(pagamento)
    session.flush()
    return pagamento
