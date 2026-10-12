"""Linktree do site (os links de grupos de WhatsApp). O ERP edita pela API pública, sem tocar no banco."""

from datetime import date

from fastapi import APIRouter, Depends, status

from app import api_publica
from app.schemas import LinkEntrada, LinkPublico
from app.security import conferir_origem, usuario_atual

router = APIRouter(
    prefix="/api/linktree",
    tags=["Linktree do site"],
    dependencies=[Depends(conferir_origem), Depends(usuario_atual)],
)


def _para_api(dados: LinkEntrada) -> dict:
    return {
        "name": dados.nome,
        "image_url": dados.imagem_url,
        "whatsapp_url": dados.whatsapp_url,
        "event_date": dados.data_evento.isoformat() if dados.data_evento else None,
        "active": dados.ativo,
        "destaque": dados.destaque,
    }


def _do_site(bruto: dict) -> LinkPublico:
    """Os dados vêm do site e podem estar fora do padrão, então não aplicamos a validação da entrada."""
    try:
        data_evento = date.fromisoformat(str(bruto.get("event_date") or "")[:10])
    except ValueError:
        data_evento = None
    return LinkPublico.model_construct(
        id=int(bruto["id"]),
        nome=str(bruto.get("name") or ""),
        imagem_url=bruto.get("image_url") or None,
        whatsapp_url=str(bruto.get("whatsapp_url") or ""),
        data_evento=data_evento,
        ativo=bool(bruto.get("active", True)),
        destaque=bool(bruto.get("destaque", False)),
    )


@router.get("")
def listar_links() -> list[LinkPublico]:
    return [_do_site(item) for item in api_publica.chamar("GET", "/linktree/all")]  # type: ignore[union-attr]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar_link(dados: LinkEntrada) -> LinkPublico:
    return _do_site(api_publica.chamar("POST", "/linktree", _para_api(dados)))  # type: ignore[arg-type]


@router.put("/{link_id}")
def atualizar_link(link_id: int, dados: LinkEntrada) -> LinkPublico:
    return _do_site(api_publica.chamar("PUT", f"/linktree/{link_id}", _para_api(dados)))  # type: ignore[arg-type]


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
def apagar_link(link_id: int) -> None:
    api_publica.chamar("DELETE", f"/linktree/{link_id}")
