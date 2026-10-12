"""Cliente da API pública (a que alimenta o site). É o único lugar do ERP que fala com ela.

O ERP usa o mesmo contrato do formulário de cadastro atual (POST/PUT/DELETE em /events e /linktree),
sem exigir nenhuma mudança na API. Se ela cair, o ERP avisa e não salva nada pela metade.
"""

import httpx

from app.config import get_settings


class ApiPublicaIndisponivel(Exception):
    """A API do site não respondeu (ou deu erro interno). Nada foi alterado."""


class ApiPublicaRecusou(Exception):
    """A API respondeu, mas recusou o pedido (dados inválidos, item que não existe...)."""

    def __init__(self, codigo: int, detalhe: str) -> None:
        super().__init__(detalhe)
        self.codigo = codigo
        self.detalhe = detalhe


def _texto_do_erro(resposta: httpx.Response) -> str:
    try:
        detalhe = resposta.json().get("detail")
    except (ValueError, AttributeError):
        detalhe = None
    if isinstance(detalhe, list) and detalhe:
        detalhe = "; ".join(str(item.get("msg", item)) for item in detalhe if isinstance(item, dict))
    return str(detalhe or f"erro {resposta.status_code}")


def chamar(metodo: str, caminho: str, corpo: dict | None = None) -> object:
    """Faz um pedido à API do site. Devolve o JSON (ou None quando não há corpo)."""
    url = f"{get_settings().api_publica}{caminho}"
    try:
        resposta = httpx.request(metodo, url, json=corpo, timeout=15)
    except httpx.HTTPError as erro:
        raise ApiPublicaIndisponivel from erro
    if resposta.status_code >= 500:
        raise ApiPublicaIndisponivel
    if resposta.status_code >= 400:
        raise ApiPublicaRecusou(resposta.status_code, _texto_do_erro(resposta))
    if resposta.status_code == 204 or not resposta.content:
        return None
    try:
        return resposta.json()
    except ValueError as erro:
        raise ApiPublicaIndisponivel from erro
