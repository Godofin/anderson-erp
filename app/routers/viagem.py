"""Fechar a van e conferir quem está nela em cada ponto da viagem (entrada, paradas, volta)."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import SessionDep
from app.models import Ponto, Reserva, Veiculo
from app.schemas import ListaDaViagem, PontoEntrada, PresencaEntrada, VeiculoDetalhe
from app.security import UsuarioAtual, conferir_origem, usuario_atual
from app.services import viagem as regras
from app.services.apresentacao import detalhe_veiculo

router = APIRouter(
    prefix="/api",
    tags=["Van fechada e presença"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _veiculo_ou_404(session: SessionDep, veiculo_id: int) -> Veiculo:
    veiculo = session.get(Veiculo, veiculo_id)
    if veiculo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Veículo não encontrado.")
    return veiculo


def _ponto_ou_404(session: SessionDep, ponto_id: int) -> Ponto:
    ponto = session.get(Ponto, ponto_id)
    if ponto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ponto de conferência não encontrado.")
    return ponto


def _lista(session: SessionDep, veiculo_id: int) -> ListaDaViagem:
    session.commit()
    return regras.montar_lista(session, _veiculo_ou_404(session, veiculo_id))


@router.post("/veiculos/{veiculo_id}/fechar")
def fechar_van(veiculo_id: int, usuario: UsuarioAtual, session: SessionDep) -> VeiculoDetalhe:
    """Fecha a lista de passageiros. A van passa a servir de lista de presença."""
    veiculo = regras.fechar(session, veiculo_id, usuario.nome)
    session.commit()
    session.refresh(veiculo)
    return detalhe_veiculo(session, veiculo)


@router.post("/veiculos/{veiculo_id}/reabrir")
def reabrir_van(veiculo_id: int, session: SessionDep) -> VeiculoDetalhe:
    """Volta a permitir mudanças na lista. Os checks já feitos continuam guardados."""
    veiculo = regras.reabrir(session, veiculo_id)
    session.commit()
    session.refresh(veiculo)
    return detalhe_veiculo(session, veiculo)


@router.get("/veiculos/{veiculo_id}/lista")
def lista_de_presenca(veiculo_id: int, session: SessionDep) -> ListaDaViagem:
    return regras.montar_lista(session, _veiculo_ou_404(session, veiculo_id))


@router.post("/veiculos/{veiculo_id}/pontos", status_code=status.HTTP_201_CREATED)
def criar_ponto(veiculo_id: int, dados: PontoEntrada, session: SessionDep) -> ListaDaViagem:
    regras.criar_ponto(session, veiculo_id, dados.nome)
    return _lista(session, veiculo_id)


@router.patch("/pontos/{ponto_id}")
def renomear_ponto(ponto_id: int, dados: PontoEntrada, session: SessionDep) -> ListaDaViagem:
    ponto = regras.renomear_ponto(session, _ponto_ou_404(session, ponto_id), dados.nome)
    return _lista(session, ponto.veiculo_id)


@router.delete("/pontos/{ponto_id}")
def apagar_ponto(ponto_id: int, session: SessionDep) -> ListaDaViagem:
    ponto = _ponto_ou_404(session, ponto_id)
    veiculo_id = ponto.veiculo_id
    regras.apagar_ponto(session, ponto)
    return _lista(session, veiculo_id)


@router.put("/pontos/{ponto_id}/presencas/{reserva_id}")
def marcar_presenca(
    ponto_id: int, reserva_id: int, dados: PresencaEntrada, usuario: UsuarioAtual, session: SessionDep
) -> ListaDaViagem:
    """Marca (ou desmarca) um passageiro neste ponto. Repetir o mesmo pedido não muda nada."""
    ponto = _ponto_ou_404(session, ponto_id)
    reserva = session.get(Reserva, reserva_id)
    if reserva is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva não encontrada.")
    regras.marcar(session, ponto, reserva, dados.presente, usuario.nome)
    return _lista(session, ponto.veiculo_id)


@router.post("/pontos/{ponto_id}/presencas")
def marcar_todos(
    ponto_id: int, dados: PresencaEntrada, usuario: UsuarioAtual, session: SessionDep
) -> ListaDaViagem:
    """Marca (ou desmarca) todos os confirmados da van neste ponto."""
    ponto = _ponto_ou_404(session, ponto_id)
    regras.marcar_todos(session, ponto, dados.presente, usuario.nome)
    return _lista(session, ponto.veiculo_id)
