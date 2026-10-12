"""Login por cookie de sessão: senha com Argon2, sessão em JWT assinado, cookie HttpOnly."""

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from pwdlib import PasswordHash
from sqlmodel import select

from app.config import get_settings
from app.db import SessionDep
from app.models import Usuario

COOKIE = "erp_sessao"
senhas = PasswordHash.recommended()  # Argon2

# Hash de uma senha qualquer, usado para gastar o mesmo tempo quando o e-mail não existe.
_HASH_FALSO = senhas.hash("sem-usuario")


def gerar_hash(senha: str) -> str:
    return senhas.hash(senha)


def verificar_senha(senha: str, hash_guardado: str | None) -> bool:
    return senhas.verify(senha, hash_guardado or _HASH_FALSO) and hash_guardado is not None


def criar_token(usuario_id: int) -> str:
    cfg = get_settings()
    expira = datetime.now(UTC) + timedelta(hours=cfg.sessao_horas)
    return jwt.encode({"sub": str(usuario_id), "exp": expira}, cfg.secret_key, algorithm="HS256")


def ler_token(token: str) -> int | None:
    try:
        dados = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
        return int(dados["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


def usuario_atual(
    session: SessionDep,
    token: Annotated[str | None, Cookie(alias=COOKIE)] = None,
) -> Usuario:
    nao_autorizado = HTTPException(status.HTTP_401_UNAUTHORIZED, "Entre para continuar.")
    if not token:
        raise nao_autorizado
    usuario_id = ler_token(token)
    usuario = session.get(Usuario, usuario_id) if usuario_id else None
    if usuario is None or not usuario.ativo:
        raise nao_autorizado
    return usuario


UsuarioAtual = Annotated[Usuario, Depends(usuario_atual)]


def conferir_origem(request: Request) -> None:
    """Defesa extra contra CSRF: pedidos que alteram dados só valem se vierem desta própria página."""
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origem = request.headers.get("origin")
    if origem and origem.split("://", 1)[-1] != request.headers.get("host"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origem não permitida.")


def buscar_por_email(session: SessionDep, email: str) -> Usuario | None:
    return session.exec(select(Usuario).where(Usuario.email == email.lower())).first()


class LimitadorDeLogin:
    """Barra tentativas em excesso (5 erros em 15 min por e-mail e endereço).

    Fica em memória: vale para um processo só. Na Vercel (serverless) cada instância tem o seu,
    então é uma barreira parcial; a senha com Argon2 continua sendo a defesa principal.
    """

    janela = 15 * 60
    maximo = 5

    def __init__(self) -> None:
        self._falhas: dict[str, list[float]] = {}
        self._trava = threading.Lock()

    def _recentes(self, chave: str) -> list[float]:
        agora = time.monotonic()
        lista = [t for t in self._falhas.get(chave, []) if agora - t < self.janela]
        self._falhas[chave] = lista
        return lista

    def bloqueado(self, chave: str) -> bool:
        with self._trava:
            return len(self._recentes(chave)) >= self.maximo

    def registrar_falha(self, chave: str) -> None:
        with self._trava:
            self._recentes(chave).append(time.monotonic())

    def limpar(self, chave: str) -> None:
        with self._trava:
            self._falhas.pop(chave, None)


limitador = LimitadorDeLogin()
