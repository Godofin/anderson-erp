from tests.conftest import SENHA


def test_rotas_exigem_login(client):
    for rota in ("/api/painel", "/api/eventos", "/api/passageiros", "/api/contatos", "/api/veiculos/1"):
        assert client.get(rota).status_code == 401, rota


def test_login_com_senha_errada(client, usuario):
    r = client.post("/api/auth/login", json={"email": "equipe@exemplo.com", "senha": "errada"})
    assert r.status_code == 401
    assert "incorretos" in r.json()["detail"]


def test_login_com_email_inexistente_nao_revela_nada(client, usuario):
    r = client.post("/api/auth/login", json={"email": "ninguem@exemplo.com", "senha": SENHA})
    assert r.status_code == 401
    assert r.json()["detail"] == "E-mail ou senha incorretos."


def test_login_correto_cria_cookie_httponly(client, usuario):
    r = client.post("/api/auth/login", json={"email": "Equipe@Exemplo.com", "senha": SENHA})
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
    assert client.get("/api/auth/eu").json()["email"] == "equipe@exemplo.com"
    assert "senha" not in r.text.lower()


def test_logout_encerra_a_sessao(logado):
    assert logado.post("/api/auth/logout").status_code == 204
    assert logado.get("/api/auth/eu").status_code == 401


def test_cookie_adulterado_nao_entra(client, usuario):
    client.cookies.set("erp_sessao", "isto.nao.e-um-token")
    assert client.get("/api/painel").status_code == 401


def test_bloqueia_depois_de_muitas_tentativas(client, usuario):
    for _ in range(5):
        assert (
            client.post("/api/auth/login", json={"email": "equipe@exemplo.com", "senha": "x"}).status_code
            == 401
        )
    r = client.post("/api/auth/login", json={"email": "equipe@exemplo.com", "senha": SENHA})
    assert r.status_code == 429


def test_pedido_de_outra_origem_e_recusado(logado):
    r = logado.post(
        "/api/contatos",
        json={"nome": "Teste", "categoria": "outro"},
        headers={"Origin": "http://site-malicioso.example"},
    )
    assert r.status_code == 403


def test_cabecalhos_de_seguranca(logado):
    r = logado.get("/api/painel")
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "default-src 'self'" in r.headers["content-security-policy"]
    assert r.headers["cache-control"] == "no-store"


def test_producao_recusa_chave_de_exemplo_ou_curta():
    import pytest

    from app.config import CHAVE_DE_EXEMPLO, Settings

    with pytest.raises(RuntimeError):
        Settings(ambiente="prod", secret_key=CHAVE_DE_EXEMPLO).validar_para_producao()
    with pytest.raises(RuntimeError):
        Settings(ambiente="prod", secret_key="curta").validar_para_producao()
    Settings(ambiente="prod", secret_key="x" * 40).validar_para_producao()  # não levanta
    Settings(ambiente="dev", secret_key="curta").validar_para_producao()  # em dev tudo bem


def test_login_aceita_conta_com_email_fora_do_padrao(client):
    from sqlmodel import Session

    from app.db import engine
    from app.models import Usuario
    from app.security import gerar_hash

    with Session(engine) as s:
        s.add(Usuario(email="admin@erp.local", nome="Admin", senha_hash=gerar_hash(SENHA)))
        s.commit()
    assert (
        client.post("/api/auth/login", json={"email": "admin@erp.local", "senha": SENHA}).status_code == 200
    )


def test_cli_recusa_email_invalido(monkeypatch, capsys):
    import argparse

    from app.cli import criar_usuario

    monkeypatch.setenv("ERP_NOVA_SENHA", "uma-senha-bem-grande-123")
    args = argparse.Namespace(email="admin@erp.local", nome="Admin")
    assert criar_usuario(args) == 1
    assert "E-mail inválido" in capsys.readouterr().err
