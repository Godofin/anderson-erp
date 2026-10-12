from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import func, select

from app.db import SessionDep
from app.eventos_publicos import obter_evento
from app.models import Contato, Reserva, Veiculo, agora
from app.schemas import ReservaEntrada, ReservaPublica, VeiculoAtualizacao, VeiculoDetalhe, VeiculoEntrada
from app.security import conferir_origem, usuario_atual
from app.services import reservas as regras
from app.services.apresentacao import detalhe_veiculo, montar_reservas

router = APIRouter(
    prefix="/api/veiculos",
    tags=["Vans e ônibus"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _veiculo_ou_404(session: SessionDep, veiculo_id: int) -> Veiculo:
    veiculo = session.get(Veiculo, veiculo_id)
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    return veiculo


def _conferir_contato(session: SessionDep, contato_id: int | None) -> None:
    if contato_id is not None and session.get(Contato, contato_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Contato não encontrado.")


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_veiculo(dados: VeiculoEntrada, session: SessionDep) -> VeiculoDetalhe:
    if obter_evento(dados.evento_id) is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Esse evento não existe no site. Atualize a lista."
        )
    _conferir_contato(session, dados.contato_id)
    veiculo = Veiculo(**dados.model_dump())
    session.add(veiculo)
    session.commit()
    session.refresh(veiculo)
    return detalhe_veiculo(session, veiculo)


@router.get("/{veiculo_id}")
def obter_veiculo(veiculo_id: int, session: SessionDep) -> VeiculoDetalhe:
    return detalhe_veiculo(session, _veiculo_ou_404(session, veiculo_id))


@router.patch("/{veiculo_id}")
def atualizar_veiculo(veiculo_id: int, dados: VeiculoAtualizacao, session: SessionDep) -> VeiculoDetalhe:
    veiculo = regras.bloquear_veiculo(session, veiculo_id)
    mudancas = dados.model_dump(exclude_unset=True)
    if "contato_id" in mudancas:
        _conferir_contato(session, mudancas["contato_id"])
    nova = mudancas.get("capacidade")
    if nova is not None and nova != veiculo.capacidade:
        regras.exigir_aberta(session, veiculo.id)
    if nova is not None and nova < veiculo.capacidade:
        ocupados = regras.assentos_ocupados(session, veiculo.id)
        if len(ocupados) > nova:
            raise regras.RegraDeNegocio(
                f"Há {len(ocupados)} passageiros confirmados. "
                f"Mova alguns antes de reduzir para {nova} assentos."
            )
        if ocupados and max(ocupados) > nova:
            raise regras.RegraDeNegocio(
                f"O assento {max(ocupados)} está ocupado. Troque o passageiro de assento antes de reduzir."
            )
    for campo, valor in mudancas.items():
        if valor is not None or campo in {"contato_id", "placa", "observacoes"}:
            setattr(veiculo, campo, valor)
    veiculo.atualizado_em = agora()
    session.add(veiculo)
    session.commit()
    session.refresh(veiculo)
    return detalhe_veiculo(session, veiculo)


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_veiculo(veiculo_id: int, session: SessionDep) -> None:
    veiculo = regras.bloquear_veiculo(session, veiculo_id)
    total = session.exec(select(func.count()).where(Reserva.veiculo_id == veiculo.id)).one()
    if total:
        raise regras.RegraDeNegocio("Há passageiros nesta van. Transfira ou remova todos antes de apagar.")
    session.delete(veiculo)
    session.commit()


@router.post("/{veiculo_id}/reservas", status_code=status.HTTP_201_CREATED)
def adicionar_passageiro(veiculo_id: int, dados: ReservaEntrada, session: SessionDep) -> ReservaPublica:
    """Coloca o passageiro na van. Se estiver lotada (ou se pedir), vai para a lista de espera."""
    reserva = regras.adicionar_reserva(session, veiculo_id, dados)
    session.commit()
    session.refresh(reserva)
    return montar_reservas(session, [reserva])[0]
