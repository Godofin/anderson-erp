from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.api_publica import ApiPublicaIndisponivel, ApiPublicaRecusou
from app.config import get_settings
from app.db import criar_tabelas
from app.routers import auth, contatos, eventos, linktree, painel, passageiros, reservas, veiculos, viagem

PASTA_FRONTEND = Path(__file__).resolve().parent.parent / "frontend"

CSP = (
    "default-src 'self'; img-src 'self' https: data:; script-src 'self'; style-src 'self'; "
    "font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI) -> AsyncIterator[None]:
    get_settings().validar_para_producao()
    criar_tabelas()
    yield


# Na importação (e não só ao iniciar): a Vercel nem sempre executa o evento de inicialização
get_settings().validar_para_producao()
producao = get_settings().ambiente == "prod"
app = FastAPI(
    title="ERP Anderson Viagem e Turismo",
    description=(
        "ERP interno: vans e ônibus por viagem, passageiros, lista de espera, pagamentos e contatos. "
        "Cadastra e lê eventos e Linktree pela API pública do site, sem alterá-la."
    ),
    version="0.1.0",
    lifespan=ciclo_de_vida,
    # a documentação interativa só existe em desenvolvimento
    docs_url=None if producao else "/docs",
    redoc_url=None,
    openapi_url=None if producao else "/openapi.json",
)


@app.middleware("http")
async def cabecalhos_de_seguranca(request: Request, call_next):
    resposta = await call_next(request)
    resposta.headers["X-Robots-Tag"] = "noindex, nofollow"
    resposta.headers["X-Content-Type-Options"] = "nosniff"
    resposta.headers["Referrer-Policy"] = "same-origin"
    if not request.url.path.startswith(("/docs", "/openapi")):
        resposta.headers["Content-Security-Policy"] = CSP
    if request.url.path.startswith("/api"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.exception_handler(ApiPublicaIndisponivel)
async def api_do_site_fora_do_ar(_: Request, __: ApiPublicaIndisponivel) -> JSONResponse:
    return JSONResponse(
        {"detail": "A API do site não respondeu agora. Nada foi alterado. Tente de novo em instantes."},
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.exception_handler(ApiPublicaRecusou)
async def api_do_site_recusou(_: Request, erro: ApiPublicaRecusou) -> JSONResponse:
    codigo = status.HTTP_404_NOT_FOUND if erro.codigo == 404 else status.HTTP_502_BAD_GATEWAY
    return JSONResponse({"detail": f"O site recusou o pedido: {erro.detalhe}"}, status_code=codigo)


@app.exception_handler(IntegrityError)
async def conflito_no_banco(_: Request, __: IntegrityError) -> JSONResponse:
    return JSONResponse(
        {"detail": "Não foi possível salvar: alguém alterou os mesmos dados. Atualize e tente de novo."},
        status_code=status.HTTP_409_CONFLICT,
    )


@app.get("/api/saude", tags=["Status"])
def saude() -> dict[str, str]:
    return {"status": "ok"}


for rota in (auth, painel, eventos, linktree, veiculos, viagem, reservas, passageiros, contatos):
    app.include_router(rota.router)

# O painel (HTML, CSS e JS) é servido pela própria API. As rotas /api vêm primeiro.
app.frontend("/", directory=PASTA_FRONTEND)
