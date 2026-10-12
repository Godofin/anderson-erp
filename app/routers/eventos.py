from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import func, select

from app import api_publica
from app.db import SessionDep
from app.eventos_publicos import limpar_cache, obter_bruto, obter_evento, obter_eventos
from app.models import Veiculo
from app.schemas import (
    EventoDetalhe,
    EventoResumo,
    EventoSiteEntrada,
    EventoSiteFicha,
    VisibilidadeEntrada,
)
from app.security import conferir_origem, usuario_atual
from app.services.apresentacao import resumo_eventos
from app.services.eventos_site import ficha_do_evento, montar_pedido
from app.services.reservas import RegraDeNegocio

router = APIRouter(
    prefix="/api/eventos",
    tags=["Eventos"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)

Filtro = Literal["proximos", "fora_do_site", "encerrados", "todos"]


@router.get("")
def listar_eventos(
    session: SessionDep,
    filtro: Annotated[Filtro, Query()] = "proximos",
    q: Annotated[str | None, Query(max_length=80)] = None,
) -> list[EventoResumo]:
    """Os eventos do site. Cada evento que abre lá aparece aqui sozinho, pronto para receber vans."""
    hoje = date.today()
    eventos = obter_eventos()
    if filtro == "proximos":
        eventos = [e for e in eventos if e.ativo and (e.data_fim is None or e.data_fim >= hoje)]
    elif filtro == "fora_do_site":
        eventos = [e for e in eventos if not e.ativo and (e.data_fim is None or e.data_fim >= hoje)]
    elif filtro == "encerrados":
        eventos = [e for e in eventos if e.data_fim is not None and e.data_fim < hoje]
    if q:
        termo = q.strip().lower()
        eventos = [e for e in eventos if termo in e.titulo_completo.lower() or termo in e.data_texto.lower()]
    eventos = sorted(eventos, key=lambda e: (e.data_inicio is None, e.data_inicio or date.max, e.id))
    resumos, _ = resumo_eventos(session, eventos)
    return resumos


@router.get("/{evento_id}")
def obter_um_evento(evento_id: int, session: SessionDep) -> EventoDetalhe:
    evento = obter_evento(evento_id)
    if evento is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento não encontrado.")
    resumos, por_evento = resumo_eventos(session, [evento])
    return EventoDetalhe(**resumos[0].model_dump(), lista_de_veiculos=por_evento.get(evento.id, []))


# ------------------------------------------------------------------ cadastro de eventos do site
def _vans_do_evento(session: SessionDep, evento_id: int) -> int:
    return int(session.exec(select(func.count()).where(Veiculo.evento_id == evento_id)).one())


def _ficha(session: SessionDep, evento_id: int) -> EventoSiteFicha:
    bruto = obter_bruto(evento_id)
    if bruto is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evento não encontrado.")
    return ficha_do_evento(bruto, _vans_do_evento(session, evento_id))


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_evento(dados: EventoSiteEntrada, session: SessionDep) -> EventoSiteFicha:
    """Cadastra o evento na API do site. Nasce fora do site, a menos que `ativo` seja verdadeiro."""
    criado = api_publica.chamar("POST", "/events", montar_pedido(dados))
    limpar_cache()
    return _ficha(session, int(criado["id"]))  # type: ignore[index]


@router.get("/{evento_id}/ficha")
def ficha_do_evento_site(evento_id: int, session: SessionDep) -> EventoSiteFicha:
    return _ficha(session, evento_id)


@router.put("/{evento_id}")
def atualizar_evento(evento_id: int, dados: EventoSiteEntrada, session: SessionDep) -> EventoSiteFicha:
    _ficha(session, evento_id)  # 404 limpo se o evento não existe
    api_publica.chamar("PUT", f"/events/{evento_id}", montar_pedido(dados))
    limpar_cache()
    return _ficha(session, evento_id)


@router.patch("/{evento_id}/visibilidade")
def mudar_visibilidade(evento_id: int, dados: VisibilidadeEntrada, session: SessionDep) -> EventoSiteFicha:
    """Publica o evento no site (ativo) ou tira do site, sem apagar nada."""
    _ficha(session, evento_id)
    api_publica.chamar("PUT", f"/events/{evento_id}", {"active_event": dados.ativo})
    limpar_cache()
    return _ficha(session, evento_id)


@router.delete("/{evento_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_evento(evento_id: int, session: SessionDep) -> None:
    _ficha(session, evento_id)
    vans = _vans_do_evento(session, evento_id)
    if vans:
        raise RegraDeNegocio(
            f"Este evento tem {vans} {'van' if vans == 1 else 'vans'} no ERP. "
            "Tire o evento do site em vez de apagar, ou apague as vans antes."
        )
    api_publica.chamar("DELETE", f"/events/{evento_id}")
    limpar_cache()
