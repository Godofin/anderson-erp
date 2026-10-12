from tests.conftest import colocar, nova_van, novo_passageiro


def _van_com(c, quantos=3, capacidade=3, **extra):
    van = nova_van(c, capacidade=capacidade, **extra)
    reservas = []
    for i in range(quantos):
        r = colocar(c, van["id"], novo_passageiro(c, i)["id"])
        assert r.status_code == 201, r.text
        reservas.append(r.json())
    return van, reservas


def _lista(c, van_id):
    r = c.get(f"/api/veiculos/{van_id}/lista")
    assert r.status_code == 200, r.text
    return r.json()


def test_exige_login(client):
    assert client.post("/api/veiculos/1/fechar").status_code == 401
    assert client.get("/api/veiculos/1/lista").status_code == 401


def test_fechar_cria_os_pontos_padrao(logado):
    van, _ = _van_com(logado, 2)
    r = logado.post(f"/api/veiculos/{van['id']}/fechar")
    assert r.status_code == 200, r.text
    assert r.json()["fechada"] is True and r.json()["fechada_em"]
    lista = _lista(logado, van["id"])
    assert [p["nome"] for p in lista["pontos"]] == ["Entrada na van", "1ª parada", "2ª parada", "Volta"]
    assert [p["presentes"] for p in lista["pontos"]] == [0, 0, 0, 0]
    assert all(p["total"] == 2 for p in lista["pontos"])
    assert [p["presente_em"] for p in lista["passageiros"]] == [[], []]
    assert lista["fechada_por"] == "Equipe Teste"


def test_nao_fecha_van_sem_confirmados_nem_duas_vezes(logado):
    van = nova_van(logado)
    assert logado.post(f"/api/veiculos/{van['id']}/fechar").status_code == 409
    van, _ = _van_com(logado, 1, nome="Van 2")
    assert logado.post(f"/api/veiculos/{van['id']}/fechar").status_code == 200
    assert logado.post(f"/api/veiculos/{van['id']}/fechar").status_code == 409


def test_lista_so_existe_com_van_fechada(logado):
    van, _ = _van_com(logado, 1)
    assert logado.get(f"/api/veiculos/{van['id']}/lista").status_code == 409
    assert logado.get("/api/veiculos/999/lista").status_code == 404


def test_van_fechada_trava_a_lista_de_passageiros(logado):
    van, reservas = _van_com(logado, 2, capacidade=3)
    outra = nova_van(logado, nome="Van 2")
    logado.post(f"/api/veiculos/{van['id']}/fechar")

    novo = novo_passageiro(logado, 5)
    assert colocar(logado, van["id"], novo["id"]).status_code == 409
    rid = reservas[0]["id"]
    assert logado.post(f"/api/reservas/{rid}/cancelar").status_code == 409
    assert logado.post(f"/api/reservas/{rid}/espera").status_code == 409
    assert logado.post(f"/api/reservas/{rid}/transferir", json={"veiculo_id": outra["id"]}).status_code == 409
    assert logado.patch(f"/api/reservas/{rid}", json={"assento": 3}).status_code == 409
    assert logado.delete(f"/api/reservas/{rid}").status_code == 409
    assert logado.patch(f"/api/veiculos/{van['id']}", json={"capacidade": 10}).status_code == 409
    # entrar numa van fechada, vindo de outra, também não
    de_fora = colocar(logado, outra["id"], novo["id"]).json()
    r = logado.post(f"/api/reservas/{de_fora['id']}/transferir", json={"veiculo_id": van["id"]})
    assert r.status_code == 409
    assert "fechada" in r.json()["detail"]


def test_van_fechada_ainda_aceita_pagamento_e_mudanca_de_nome(logado):
    van, reservas = _van_com(logado, 1)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    rid = reservas[0]["id"]
    assert logado.post(f"/api/reservas/{rid}/quitar", json={}).status_code == 201
    assert logado.patch(f"/api/veiculos/{van['id']}", json={"nome": "Van do Zé"}).status_code == 200


def test_marcar_presenca_em_cada_ponto(logado):
    van, reservas = _van_com(logado, 3)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    pontos = _lista(logado, van["id"])["pontos"]
    entrada, parada1 = pontos[0]["id"], pontos[1]["id"]
    a, b = reservas[0]["id"], reservas[1]["id"]

    r = logado.put(f"/api/pontos/{entrada}/presencas/{a}", json={"presente": True})
    assert r.status_code == 200, r.text
    assert logado.put(f"/api/pontos/{entrada}/presencas/{b}", json={"presente": True}).status_code == 200
    lista = logado.put(f"/api/pontos/{parada1}/presencas/{a}", json={"presente": True}).json()

    por_id = {p["id"]: p for p in lista["pontos"]}
    assert por_id[entrada]["presentes"] == 2 and por_id[parada1]["presentes"] == 1
    do_a = next(p for p in lista["passageiros"] if p["id"] == a)
    assert sorted(do_a["presente_em"]) == sorted([entrada, parada1])

    # repetir o mesmo pedido não duplica; desmarcar tira
    logado.put(f"/api/pontos/{entrada}/presencas/{a}", json={"presente": True})
    assert _lista(logado, van["id"])["pontos"][0]["presentes"] == 2
    lista = logado.put(f"/api/pontos/{entrada}/presencas/{a}", json={"presente": False}).json()
    assert lista["pontos"][0]["presentes"] == 1


def test_marcar_todos_e_desmarcar_todos(logado):
    van, _ = _van_com(logado, 3)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    ponto = _lista(logado, van["id"])["pontos"][0]["id"]
    lista = logado.post(f"/api/pontos/{ponto}/presencas", json={"presente": True}).json()
    assert lista["pontos"][0]["presentes"] == 3
    lista = logado.post(f"/api/pontos/{ponto}/presencas", json={"presente": False}).json()
    assert lista["pontos"][0]["presentes"] == 0


def test_so_marca_confirmado_da_propria_van(logado):
    van, reservas = _van_com(logado, 1, capacidade=1)
    espera = colocar(logado, van["id"], novo_passageiro(logado, 4)["id"]).json()
    assert espera["situacao"] == "espera"
    outra, outras = _van_com_outra(logado)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    ponto = _lista(logado, van["id"])["pontos"][0]["id"]
    assert (
        logado.put(f"/api/pontos/{ponto}/presencas/{espera['id']}", json={"presente": True}).status_code
        == 409
    )
    assert (
        logado.put(f"/api/pontos/{ponto}/presencas/{outras[0]['id']}", json={"presente": True}).status_code
        == 409
    )
    assert logado.put(f"/api/pontos/{ponto}/presencas/9999", json={"presente": True}).status_code == 404
    assert _lista(logado, van["id"])["fora_da_lista"] == 1


def _van_com_outra(c):
    van = nova_van(c, nome="Van B", capacidade=2)
    r = colocar(c, van["id"], novo_passageiro(c, 3)["id"])
    return van, [r.json()]


def test_nao_marca_com_a_van_aberta(logado):
    van, reservas = _van_com(logado, 1)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    ponto = _lista(logado, van["id"])["pontos"][0]["id"]
    logado.post(f"/api/veiculos/{van['id']}/reabrir")
    r = logado.put(f"/api/pontos/{ponto}/presencas/{reservas[0]['id']}", json={"presente": True})
    assert r.status_code == 409


def test_reabrir_mantem_os_checks_e_libera_a_lista(logado):
    van, reservas = _van_com(logado, 2, capacidade=3)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    ponto = _lista(logado, van["id"])["pontos"][0]["id"]
    logado.put(f"/api/pontos/{ponto}/presencas/{reservas[0]['id']}", json={"presente": True})

    r = logado.post(f"/api/veiculos/{van['id']}/reabrir")
    assert r.status_code == 200 and r.json()["fechada"] is False
    assert logado.post(f"/api/veiculos/{van['id']}/reabrir").status_code == 409
    assert colocar(logado, van["id"], novo_passageiro(logado, 4)["id"]).status_code == 201

    logado.post(f"/api/veiculos/{van['id']}/fechar")
    lista = _lista(logado, van["id"])
    assert lista["pontos"][0]["presentes"] == 1 and lista["pontos"][0]["total"] == 3


def test_pontos_criar_renomear_apagar(logado):
    van, reservas = _van_com(logado, 1)
    logado.post(f"/api/veiculos/{van['id']}/fechar")

    r = logado.post(f"/api/veiculos/{van['id']}/pontos", json={"nome": "Almoço"})
    assert r.status_code == 201, r.text
    novo = r.json()["pontos"][-1]
    assert novo["nome"] == "Almoço" and novo["ordem"] == 5

    assert logado.post(f"/api/veiculos/{van['id']}/pontos", json={"nome": "almoço"}).status_code == 409
    r = logado.patch(f"/api/pontos/{novo['id']}", json={"nome": "Parada do almoço"})
    assert r.status_code == 200 and r.json()["pontos"][-1]["nome"] == "Parada do almoço"

    logado.put(f"/api/pontos/{novo['id']}/presencas/{reservas[0]['id']}", json={"presente": True})
    r = logado.delete(f"/api/pontos/{novo['id']}")
    assert r.status_code == 200, r.text
    assert [p["nome"] for p in r.json()["pontos"]] == ["Entrada na van", "1ª parada", "2ª parada", "Volta"]
    assert all(r.json()["passageiros"][0]["presente_em"] == [] for _ in [0])


def test_limite_de_pontos(logado):
    van, _ = _van_com(logado, 1)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    for i in range(8):
        assert (
            logado.post(f"/api/veiculos/{van['id']}/pontos", json={"nome": f"Ponto extra {i}"}).status_code
            == 201
        )
    assert logado.post(f"/api/veiculos/{van['id']}/pontos", json={"nome": "Demais"}).status_code == 409


def test_resumo_do_evento_mostra_van_fechada(logado):
    van, _ = _van_com(logado, 1)
    logado.post(f"/api/veiculos/{van['id']}/fechar")
    detalhe = logado.get("/api/eventos/1").json()
    assert detalhe["lista_de_veiculos"][0]["fechada"] is True
    assert logado.get(f"/api/veiculos/{van['id']}").json()["fechada"] is True
