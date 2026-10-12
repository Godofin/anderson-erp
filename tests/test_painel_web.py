"""O ERP serve o próprio painel (HTML, CSS e JS) e não deixa nada disso ser indexado."""


def test_pagina_inicial_e_servida_sem_login(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "ERP" in r.text and 'name="robots" content="noindex, nofollow"' in r.text
    assert r.headers["x-robots-tag"] == "noindex, nofollow"
    assert "script-src 'self'" in r.headers["content-security-policy"]


def test_arquivos_do_painel_existem(client):
    for caminho in ("/js/app.js", "/css/erp.css", "/assets/logo-escuro.png", "/robots.txt"):
        assert client.get(caminho).status_code == 200, caminho
    assert "Disallow: /" in client.get("/robots.txt").text


def test_a_api_tem_prioridade_sobre_o_painel(client):
    assert client.get("/api/painel").status_code == 401  # não devolve o index.html
    assert client.get("/api/saude").json() == {"status": "ok"}


def test_documentacao_interativa_so_em_desenvolvimento(client):
    assert client.get("/docs").status_code == 200  # os testes rodam em modo dev
