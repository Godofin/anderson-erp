"""Tradução entre o formulário do ERP e o contrato da API pública (o mesmo do painel admin atual)."""

from datetime import date
from urllib.parse import quote

from app.config import get_settings
from app.schemas import EventoSiteEntrada, EventoSiteFicha

TIPO_PARA_ALT = {"show": "Shows/Eventos", "eco": "Ecoturismo/Viagens"}


def link_whatsapp(titulo: str) -> str:
    """O link do botão "Reservar" quando o destino é o WhatsApp (igual ao que o painel atual gera)."""
    mensagem = f"Olá! Tenho interesse na excursão para o evento {titulo}. Gostaria de mais informações."
    # encodeURIComponent do navegador deixa estes caracteres sem codificar
    return (
        f"https://api.whatsapp.com/send?phone={get_settings().whatsapp_numero}"
        f"&text={quote(mensagem, safe='-_.!~*()')}"
    )


def montar_pedido(dados: EventoSiteEntrada) -> dict:
    """Corpo enviado à API pública, campo a campo como o formulário atual envia."""
    return {
        "image": dados.imagem,
        "alt": TIPO_PARA_ALT[dados.tipo],
        "title": dados.titulo,
        "date": dados.data_texto,
        "date_event": dados.data_evento.isoformat(),
        "year": str(dados.data_evento.year),
        "description": dados.descricao,
        "buttonText": dados.texto_botao,
        "eventName": dados.titulo,
        "cities": dados.cidades,
        "active_event": dados.ativo,
        "ecommerce_link": (
            dados.link_botao if dados.destino_botao == "link" else link_whatsapp(dados.titulo)
        ),
        "saiba_mais_link": dados.saiba_mais_link,
        "destaque": dados.destaque,
    }


def ficha_do_evento(bruto: dict, veiculos: int) -> EventoSiteFicha:
    """Transforma o evento da API pública nos campos do formulário de edição."""
    ecommerce = bruto.get("ecommerce_link") or ""
    numero = get_settings().whatsapp_numero
    pelo_whatsapp = not ecommerce or ("api.whatsapp.com" in ecommerce and numero in ecommerce)
    titulo = str(bruto.get("title") or bruto.get("eventName") or "")
    try:
        data_evento = date.fromisoformat(str(bruto.get("date_event") or "")[:10])
    except ValueError:
        data_evento = None
    return EventoSiteFicha(
        id=int(bruto["id"]),
        titulo=titulo,
        tipo="eco" if "ecoturismo" in str(bruto.get("alt") or "").lower() else "show",
        imagem=str(bruto.get("image") or ""),
        descricao=str(bruto.get("description") or ""),
        data_texto=str(bruto.get("date") or ""),
        data_evento=data_evento,
        texto_botao=str(bruto.get("buttonText") or "Reservar agora"),
        destino_botao="whatsapp" if pelo_whatsapp else "link",
        link_botao=None if pelo_whatsapp else ecommerce,
        cidades=[str(c) for c in (bruto.get("cities") or [])],
        saiba_mais_link=bruto.get("saiba_mais_link") or None,
        ativo=bool(bruto.get("active_event", True)),
        destaque=bool(bruto.get("destaque", False)),
        veiculos=veiculos,
        link_whatsapp=link_whatsapp(titulo),
    )
