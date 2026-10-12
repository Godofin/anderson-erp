"""Van fechada e lista de presença: fechar a lista, conferir quem está na van em cada ponto da viagem."""

from collections import defaultdict

from sqlmodel import Session, col, func, select

from app.models import Fechamento, Ponto, Presenca, Reserva, Veiculo
from app.schemas import ListaDaViagem, PassageiroDaLista, PontoPublico
from app.services.apresentacao import montar_reservas, resumo_veiculos
from app.services.reservas import RegraDeNegocio, bloquear_veiculo, van_fechada

PONTOS_PADRAO = ["Entrada na van", "1ª parada", "2ª parada", "Volta"]
MAXIMO_DE_PONTOS = 12


def fechar(session: Session, veiculo_id: int, usuario: str) -> Veiculo:
    veiculo = bloquear_veiculo(session, veiculo_id)
    if van_fechada(session, veiculo.id):
        raise RegraDeNegocio("Esta van já está fechada.")
    confirmados = session.exec(
        select(func.count()).where(Reserva.veiculo_id == veiculo.id, Reserva.situacao == "confirmado")
    ).one()
    if not confirmados:
        raise RegraDeNegocio("Não há passageiros confirmados nesta van. Não há o que fechar.")
    session.add(Fechamento(veiculo_id=veiculo.id, fechada_por=usuario))
    tem_pontos = session.exec(select(func.count()).where(Ponto.veiculo_id == veiculo.id)).one()
    if not tem_pontos:
        for ordem, nome in enumerate(PONTOS_PADRAO, start=1):
            session.add(Ponto(veiculo_id=veiculo.id, nome=nome, ordem=ordem))
    session.flush()
    return veiculo


def reabrir(session: Session, veiculo_id: int) -> Veiculo:
    veiculo = bloquear_veiculo(session, veiculo_id)
    fechamento = session.get(Fechamento, veiculo.id)
    if fechamento is None:
        raise RegraDeNegocio("Esta van não está fechada.")
    session.delete(fechamento)  # os pontos e os checks ficam guardados, para o caso de fechar de novo
    session.flush()
    return veiculo


def exigir_fechada(session: Session, veiculo_id: int) -> Fechamento:
    fechamento = session.get(Fechamento, veiculo_id)
    if fechamento is None:
        raise RegraDeNegocio("Feche a van para usar a lista de presença.")
    return fechamento


# ------------------------------------------------------------------ pontos
def criar_ponto(session: Session, veiculo_id: int, nome: str) -> Ponto:
    veiculo = bloquear_veiculo(session, veiculo_id)
    exigir_fechada(session, veiculo.id)
    existentes = session.exec(select(Ponto).where(Ponto.veiculo_id == veiculo.id)).all()
    if len(existentes) >= MAXIMO_DE_PONTOS:
        raise RegraDeNegocio(f"Cada van aceita até {MAXIMO_DE_PONTOS} pontos de conferência.")
    _conferir_nome_livre(existentes, nome)
    ponto = Ponto(veiculo_id=veiculo.id, nome=nome, ordem=max((p.ordem for p in existentes), default=0) + 1)
    session.add(ponto)
    session.flush()
    return ponto


def renomear_ponto(session: Session, ponto: Ponto, nome: str) -> Ponto:
    exigir_fechada(session, ponto.veiculo_id)
    outros = session.exec(
        select(Ponto).where(Ponto.veiculo_id == ponto.veiculo_id, Ponto.id != ponto.id)
    ).all()
    _conferir_nome_livre(outros, nome)
    ponto.nome = nome
    session.add(ponto)
    session.flush()
    return ponto


def apagar_ponto(session: Session, ponto: Ponto) -> None:
    exigir_fechada(session, ponto.veiculo_id)
    for presenca in session.exec(select(Presenca).where(Presenca.ponto_id == ponto.id)).all():
        session.delete(presenca)
    session.flush()  # as marcações saem antes do ponto, por causa da chave estrangeira
    session.delete(ponto)
    session.flush()


def _conferir_nome_livre(outros: list[Ponto], nome: str) -> None:
    if any(p.nome.strip().lower() == nome.strip().lower() for p in outros):
        raise RegraDeNegocio("Já existe um ponto com esse nome nesta van.")


# ------------------------------------------------------------------ presenças
def _confirmadas(session: Session, veiculo_id: int) -> list[Reserva]:
    return list(
        session.exec(
            select(Reserva)
            .where(Reserva.veiculo_id == veiculo_id, Reserva.situacao == "confirmado")
            .order_by(col(Reserva.assento), col(Reserva.id))
        ).all()
    )


def marcar(session: Session, ponto: Ponto, reserva: Reserva, presente: bool, usuario: str) -> None:
    exigir_fechada(session, ponto.veiculo_id)
    if reserva.veiculo_id != ponto.veiculo_id or reserva.situacao != "confirmado":
        raise RegraDeNegocio("Este passageiro não está na lista confirmada desta van.")
    atual = session.exec(
        select(Presenca).where(Presenca.ponto_id == ponto.id, Presenca.reserva_id == reserva.id)
    ).first()
    if presente and atual is None:
        session.add(Presenca(ponto_id=ponto.id, reserva_id=reserva.id, marcado_por=usuario))
    elif not presente and atual is not None:
        session.delete(atual)
    session.flush()


def marcar_todos(session: Session, ponto: Ponto, presente: bool, usuario: str) -> None:
    exigir_fechada(session, ponto.veiculo_id)
    ids = [r.id for r in _confirmadas(session, ponto.veiculo_id)]
    ja = {p.reserva_id: p for p in session.exec(select(Presenca).where(Presenca.ponto_id == ponto.id)).all()}
    for reserva_id in ids:
        if presente and reserva_id not in ja:
            session.add(Presenca(ponto_id=ponto.id, reserva_id=reserva_id, marcado_por=usuario))
        elif not presente and reserva_id in ja:
            session.delete(ja[reserva_id])
    session.flush()


# ------------------------------------------------------------------ a lista
def montar_lista(session: Session, veiculo: Veiculo) -> ListaDaViagem:
    fechamento = exigir_fechada(session, veiculo.id)
    pontos = list(
        session.exec(
            select(Ponto).where(Ponto.veiculo_id == veiculo.id).order_by(col(Ponto.ordem), col(Ponto.id))
        ).all()
    )
    confirmadas = _confirmadas(session, veiculo.id)
    publicas = montar_reservas(session, confirmadas)
    marcas = session.exec(
        select(Presenca).where(col(Presenca.ponto_id).in_([p.id for p in pontos] or [0]))
    ).all()
    por_reserva: dict[int, list[int]] = defaultdict(list)
    por_ponto: dict[int, int] = defaultdict(int)
    validas = {r.id for r in confirmadas}
    for marca in marcas:
        if marca.reserva_id in validas:
            por_reserva[marca.reserva_id].append(marca.ponto_id)
            por_ponto[marca.ponto_id] += 1
    fora = session.exec(
        select(func.count()).where(Reserva.veiculo_id == veiculo.id, Reserva.situacao == "espera")
    ).one()
    return ListaDaViagem(
        veiculo=resumo_veiculos(session, [veiculo])[0],
        fechada_em=fechamento.fechada_em,
        fechada_por=fechamento.fechada_por,
        pontos=[
            PontoPublico(
                id=p.id, nome=p.nome, ordem=p.ordem, presentes=por_ponto[p.id], total=len(confirmadas)
            )
            for p in pontos
        ],
        passageiros=[
            PassageiroDaLista(**r.model_dump(), presente_em=sorted(por_reserva.get(r.id, [])))
            for r in sorted(publicas, key=lambda r: r.assento or 0)
        ],
        fora_da_lista=int(fora),
    )
