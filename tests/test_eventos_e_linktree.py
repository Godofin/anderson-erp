from urllib.parse import parse_qs, urlparse

from tests.conftest import nova_van

FORM = {
    "titulo": "Excursão Novo Show",
    "tipo": "show",
    "imagem": "https://exemplo.com/capa.jpg",
    "descricao": "Saída de Araraquara com transporte seguro.",
    "data_texto": "10 de dezembro de 2026 - São Paulo",
    "data_evento": "2026-12-10",
    "cidades": ["Araraquara", "São Carlos", "Araraquara"],
    "saiba_mais_link": "novo_show.html",
}


def _enviados(api, metodo):
    return [(c, corpo) for m, c, corpo in api.chamadas if m == metodo]


def test_exige_login(client):
    assert client.post("/api/eventos", json=FORM).status_code == 401
    assert client.get("/api/linktree").status_code == 401


def test_criar_evento_envia_o_contrato_do_site_e_nasce_escondido(logado, api):
    r = logado.post("/api/eventos", json=FORM)
    assert r.status_code == 201, r.text
    ficha = r.json()
    assert ficha["ativo"] is False
    assert ficha["cidades"] == ["Araraquara", "São Carlos"]

    ((caminho, corpo),) = _enviados(api, "POST")
    assert caminho == "/events"
    assert corpo["title"] == corpo["eventName"] == "Excursão Novo Show"
    assert corpo["alt"] == "Shows/Eventos"
    assert corpo["date_event"] == "2026-12-10" and corpo["year"] == "2026"
    assert corpo["buttonText"] == "Reservar agora"
    assert corpo["active_event"] is False
    assert corpo["saiba_mais_link"] == "novo_show.html"

    link = urlparse(corpo["ecommerce_link"])
    assert link.netloc == "api.whatsapp.com"
    consulta = parse_qs(link.query)
    assert consulta["phone"] == ["5516988332631"]
    assert "Excursão Novo Show" in consulta["text"][0]
    assert ficha["link_whatsapp"] == corpo["ecommerce_link"]

    # já aparece na lista do ERP, sem esperar o cache
    ids = [e["id"] for e in logado.get("/api/eventos?filtro=todos").json()]
    assert ficha["id"] in ids


def test_criar_evento_com_link_proprio_e_ecoturismo(logado, api):
    dados = {**FORM, "tipo": "eco", "destino_botao": "link", "link_botao": "https://loja.exemplo.com/x"}
    r = logado.post("/api/eventos", json=dados)
    assert r.status_code == 201, r.text
    ((_, corpo),) = _enviados(api, "POST")
    assert corpo["alt"] == "Ecoturismo/Viagens"
    assert corpo["ecommerce_link"] == "https://loja.exemplo.com/x"
    ficha = r.json()
    assert ficha["destino_botao"] == "link" and ficha["tipo"] == "eco"


def test_validacoes_do_formulario(logado, api):
    for ruim in (
        {**FORM, "imagem": "javascript:alert(1)"},
        {**FORM, "titulo": "ab"},
        {**FORM, "data_evento": "10/12/2026"},
        {**FORM, "destino_botao": "link"},
        {**FORM, "destino_botao": "link", "link_botao": "ftp://x"},
        {**FORM, "saiba_mais_link": "javascript:alert(1)"},
        {**FORM, "tipo": "outro"},
    ):
        assert logado.post("/api/eventos", json=ruim).status_code == 422, ruim
    assert _enviados(api, "POST") == []


def test_editar_evento(logado, api):
    antes = logado.get("/api/eventos/1/ficha").json()
    assert antes["titulo"] == "Excursão Show Um"
    assert antes["destino_botao"] == "whatsapp"

    r = logado.put("/api/eventos/1", json={**FORM, "titulo": "Excursão Show Um Editado", "ativo": True})
    assert r.status_code == 200, r.text
    assert r.json()["titulo"] == "Excursão Show Um Editado"
    assert r.json()["ativo"] is True
    assert api.eventos[0]["title"] == "Excursão Show Um Editado"


def test_editar_evento_que_nao_existe(logado, api):
    assert logado.put("/api/eventos/999", json=FORM).status_code == 404
    assert logado.get("/api/eventos/999/ficha").status_code == 404
    assert _enviados(api, "PUT") == []


def test_publicar_e_tirar_do_site_mexe_so_na_visibilidade(logado, api):
    r = logado.patch("/api/eventos/4/visibilidade", json={"ativo": True})
    assert r.status_code == 200, r.text
    assert r.json()["ativo"] is True
    ((caminho, corpo),) = _enviados(api, "PUT")
    assert caminho == "/events/4" and corpo == {"active_event": True}

    r = logado.patch("/api/eventos/4/visibilidade", json={"ativo": False})
    assert r.json()["ativo"] is False


def test_apagar_evento_sem_vans(logado, api):
    assert logado.delete("/api/eventos/2").status_code == 204
    assert all(e["id"] != 2 for e in api.eventos)
    assert logado.get("/api/eventos/2/ficha").status_code == 404


def test_nao_apaga_evento_que_tem_vans(logado, api):
    nova_van(logado, evento_id=1)
    r = logado.delete("/api/eventos/1")
    assert r.status_code == 409
    assert "van" in r.json()["detail"]
    assert _enviados(api, "DELETE") == []
    assert logado.get("/api/eventos/1/ficha").json()["veiculos"] == 1


def test_api_do_site_fora_do_ar_nao_salva_nada(logado, api):
    logado.get("/api/eventos")  # deixa a cópia local pronta
    api.fora_do_ar = True
    r = logado.post("/api/eventos", json=FORM)
    assert r.status_code == 503
    assert "Nada foi alterado" in r.json()["detail"]


def test_api_do_site_recusa_o_pedido(logado, api):
    api.recusar_com = (422, "campo inválido")
    r = logado.post("/api/eventos", json=FORM)
    assert r.status_code == 502
    assert "campo inválido" in r.json()["detail"]


def test_linktree_criar_editar_apagar(logado, api):
    links = logado.get("/api/linktree").json()
    assert [item["nome"] for item in links] == ["Grupo Show Um"]

    novo = {
        "nome": "Grupo Dois",
        "whatsapp_url": "https://chat.whatsapp.com/xyz",
        "data_evento": "2026-12-10",
    }
    r = logado.post("/api/linktree", json=novo)
    assert r.status_code == 201, r.text
    criado = r.json()
    assert criado["nome"] == "Grupo Dois" and criado["ativo"] is True
    assert api.links[-1]["whatsapp_url"] == "https://chat.whatsapp.com/xyz"
    assert api.links[-1]["event_date"] == "2026-12-10"

    r = logado.put(f"/api/linktree/{criado['id']}", json={**novo, "nome": "Grupo Dois B", "ativo": False})
    assert r.status_code == 200 and r.json()["ativo"] is False

    assert logado.delete(f"/api/linktree/{criado['id']}").status_code == 204
    assert [item["id"] for item in logado.get("/api/linktree").json()] == [1]


def test_linktree_recusa_link_invalido(logado):
    r = logado.post("/api/linktree", json={"nome": "X", "whatsapp_url": "javascript:alert(1)"})
    assert r.status_code == 422


def test_filtro_fora_do_site_mostra_o_que_ainda_nao_foi_publicado(logado):
    criado = logado.post("/api/eventos", json=FORM).json()
    titulos = [e["titulo"] for e in logado.get("/api/eventos", params={"filtro": "fora_do_site"}).json()]
    assert "Show Desativado" in titulos and criado["titulo"].replace("Excursão ", "") in titulos
    assert "Show Um" not in titulos and "Show Passado" not in titulos
