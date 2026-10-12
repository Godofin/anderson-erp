"""Leitura dos eventos da API pública (a que alimenta o site), com cache curto.

A escrita fica em routers/eventos.py. Um evento cadastrado pelo painel antigo aparece aqui sozinho,
em até ERP_EVENTOS_CACHE_SEGUNDOS, pronto para receber vans.
"""

import re
import threading
import time
from datetime import date

from pydantic import BaseModel

from app import api_publica
from app.api_publica import ApiPublicaIndisponivel
from app.config import get_settings
from app.services.datas import ler_datas

CORRECOES_DE_CIDADE = {"araraqura": "Araraquara"}


# Nome antigo, mantido porque várias partes do código usam. É o mesmo erro do cliente da API.
EventosIndisponiveis = ApiPublicaIndisponivel


class EventoPublico(BaseModel):
    id: int
    titulo: str
    titulo_completo: str
    data_texto: str
    data_inicio: date | None
    data_fim: date | None
    imagem: str | None
    ativo: bool
    destaque: bool
    tipo: str
    cidades: list[str]


_cache: dict[str, object] = {"quando": 0.0, "brutos": None}
_trava = threading.Lock()


def _limpar_cidades(bruto: list[str] | None) -> list[str]:
    cidades: list[str] = []
    for item in bruto or []:
        for parte in re.split(r",|\s+e\s+", str(item)):
            nome = re.sub(r"[!.]+$", "", parte).strip()
            if nome:
                nome = CORRECOES_DE_CIDADE.get(nome.lower(), nome)
                if nome not in cidades:
                    cidades.append(nome)
    return cidades


def _converter(bruto: dict) -> EventoPublico:
    completo = re.sub(
        r"\s*[—–]\s*", " - ", str(bruto.get("title") or bruto.get("eventName") or "Evento")
    ).strip()
    curto = re.sub(r"^\s*excurs[aã]o\s+(oficial\s+)?", "", completo, flags=re.IGNORECASE).strip() or completo
    texto = re.sub(r"\s*[—–]\s*", " - ", str(bruto.get("date") or ""))
    inicio, fim = ler_datas(texto, bruto.get("date_event"), bruto.get("year"))
    return EventoPublico(
        id=int(bruto["id"]),
        titulo=curto,
        titulo_completo=completo,
        data_texto=texto,
        data_inicio=inicio,
        data_fim=fim,
        imagem=bruto.get("image") or None,
        ativo=bool(bruto.get("active_event", True)),
        destaque=bool(bruto.get("destaque", False)),
        tipo="eco" if "ecoturismo" in str(bruto.get("alt") or "").lower() else "show",
        cidades=_limpar_cidades(bruto.get("cities")),
    )


def obter_brutos(forcar: bool = False) -> list[dict]:
    """Eventos exatamente como a API pública entrega (todos os campos), com cache curto."""
    cfg = get_settings()
    with _trava:
        guardado = _cache["brutos"]
        recente = time.monotonic() - _cache["quando"] < cfg.eventos_cache_segundos  # type: ignore[operator]
        if not forcar and guardado is not None and recente:
            return guardado  # type: ignore[return-value]
    try:
        brutos = api_publica.chamar("GET", "/events/all")
        if not isinstance(brutos, list):
            raise ApiPublicaIndisponivel
        [_converter(item) for item in brutos]  # confere o formato antes de guardar
    except (ApiPublicaIndisponivel, KeyError, TypeError, ValueError) as erro:
        with _trava:
            if _cache["brutos"] is not None:  # a API caiu: usa a última cópia boa
                return _cache["brutos"]  # type: ignore[return-value]
        raise ApiPublicaIndisponivel from erro
    with _trava:
        _cache["brutos"] = brutos
        _cache["quando"] = time.monotonic()
    return brutos


def obter_eventos(forcar: bool = False) -> list[EventoPublico]:
    return [_converter(item) for item in obter_brutos(forcar)]


def obter_bruto(evento_id: int) -> dict | None:
    return next((e for e in obter_brutos() if int(e["id"]) == evento_id), None)


def obter_evento(evento_id: int) -> EventoPublico | None:
    return next((e for e in obter_eventos() if e.id == evento_id), None)


def limpar_cache() -> None:
    with _trava:
        _cache["brutos"] = None
        _cache["quando"] = 0.0
