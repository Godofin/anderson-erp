from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import get_settings
from app.db import SessionDep
from app.schemas import LoginEntrada, UsuarioPublico
from app.security import (
    COOKIE,
    UsuarioAtual,
    buscar_por_email,
    conferir_origem,
    criar_token,
    limitador,
    verificar_senha,
)

router = APIRouter(prefix="/api/auth", tags=["Autenticação"], dependencies=[Depends(conferir_origem)])


@router.post("/login")
def entrar(dados: LoginEntrada, request: Request, response: Response, session: SessionDep) -> UsuarioPublico:
    cfg = get_settings()
    endereco = request.client.host if request.client else "-"
    chave = f"{dados.email.lower()}|{endereco}"
    if limitador.bloqueado(chave):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Muitas tentativas. Espere alguns minutos e tente de novo."
        )
    usuario = buscar_por_email(session, dados.email)
    valido = usuario is not None and usuario.ativo
    if not verificar_senha(dados.senha, usuario.senha_hash if valido else None):
        limitador.registrar_falha(chave)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    limitador.limpar(chave)
    response.set_cookie(
        COOKIE,
        criar_token(usuario.id),
        max_age=cfg.sessao_horas * 3600,
        httponly=True,
        samesite="strict",
        secure=cfg.ambiente == "prod",
        path="/",
    )
    return UsuarioPublico(id=usuario.id, email=usuario.email, nome=usuario.nome)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def sair(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


@router.get("/eu")
def quem_sou_eu(usuario: UsuarioAtual) -> UsuarioPublico:
    return UsuarioPublico(id=usuario.id, email=usuario.email, nome=usuario.nome)
