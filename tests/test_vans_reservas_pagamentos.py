from datetime import date, timedelta

from tests.conftest import colocar, nova_van, novo_passageiro


def detalhe(c, van_id):
    return c.get(f"/api/veiculos/{van_id}").json()


# ---------------------------------------------------------------- eventos
def test_eventos_do_site_aparecem_sozinhos(logado):
    titulos = [e["titulo"] for e in logado.get("/api/eventos").json()]
    assert titulos == ["Show Um", "Show Dois"]  # ordenados por data; sem o passado e sem o desativado


def test_filtros_de_eventos(logado):
    assert [e["titulo"] for e in logado.get("/api/eventos", params={"filtro": "encerrados"}).json()] == [
        "Show Passado"
    ]
    assert len(logado.get("/api/eventos", params={"filtro": "todos"}).json()) == 4


def test_cidade_com_erro_de_digitacao_e_corrigida(logado):
    assert logado.get("/api/eventos/1").json()["cidades"] == ["Araraquara", "São Carlos"]


def test_evento_inexistente(logado):
    assert logado.get("/api/eventos/999").status_code == 404


# ---------------------------------------------------------------- vans
def test_criar_van_com_evento_que_nao_existe_no_site(logado):
    r = logado.post("/api/veiculos", json={"evento_id": 999, "nome": "Van", "tipo": "van", "capacidade": 10})
    assert r.status_code == 422


def test_van_nova_aparece_no_evento(logado):
    nova_van(logado, capacidade=15)
    evento = logado.get("/api/eventos/1").json()
    assert evento["veiculos"] == 1 and evento["assentos"] == 15
    assert evento["lista_de_veiculos"][0]["livres"] == 15


def test_capacidade_invalida(logado):
    r = logado.post("/api/veiculos", json={"evento_id": 1, "nome": "Van", "tipo": "van", "capacidade": 0})
    assert r.status_code == 422
    r = logado.post("/api/veiculos", json={"evento_id": 1, "nome": "Van", "tipo": "trem", "capacidade": 5})
    assert r.status_code == 422


def test_van_pode_ter_motorista_dos_contatos(logado):
    contato = logado.post(
        "/api/contatos", json={"nome": "Seu Raimundo", "categoria": "motorista", "telefone": "16 99999-0000"}
    ).json()
    van = nova_van(logado, contato_id=contato["id"])
    assert van["contato"]["nome"] == "Seu Raimundo"
    assert logado.get("/api/contatos").json()[0]["veiculos"] == 1


def test_nao_reduz_capacidade_abaixo_dos_confirmados(logado):
    van = nova_van(logado, capacidade=3)
    for i in range(3):
        colocar(logado, van["id"], novo_passageiro(logado, i)["id"])
    r = logado.patch(f"/api/veiculos/{van['id']}", json={"capacidade": 2})
    assert r.status_code == 409


def test_nao_reduz_capacidade_com_assento_alto_ocupado(logado):
    van = nova_van(logado, capacidade=5)
    p = novo_passageiro(logado, 0)
    colocar(logado, van["id"], p["id"], assento=5)
    r = logado.patch(f"/api/veiculos/{van['id']}", json={"capacidade": 4})
    assert r.status_code == 409 and "assento 5" in r.json()["detail"]


def test_nao_apaga_van_com_passageiros(logado):
    van = nova_van(logado)
    colocar(logado, van["id"], novo_passageiro(logado, 0)["id"])
    assert logado.delete(f"/api/veiculos/{van['id']}").status_code == 409


def test_apaga_van_vazia(logado):
    van = nova_van(logado)
    assert logado.delete(f"/api/veiculos/{van['id']}").status_code == 204


# ---------------------------------------------------------------- reservas, assentos e lista de espera
def test_passageiros_recebem_assentos_em_ordem(logado):
    van = nova_van(logado, capacidade=3)
    for i in range(3):
        r = colocar(logado, van["id"], novo_passageiro(logado, i)["id"])
        assert r.json()["situacao"] == "confirmado"
        assert r.json()["assento"] == i + 1


def test_van_lotada_manda_para_a_lista_de_espera_na_ordem(logado):
    van = nova_van(logado, capacidade=2)
    situacoes = []
    for i in range(4):
        r = colocar(logado, van["id"], novo_passageiro(logado, i)["id"]).json()
        situacoes.append((r["situacao"], r["posicao_espera"]))
    assert situacoes == [("confirmado", None), ("confirmado", None), ("espera", 1), ("espera", 2)]
    d = detalhe(logado, van["id"])
    assert d["confirmados"] == 2 and d["livres"] == 0 and d["em_espera"] == 2
    assert [r["posicao_espera"] for r in d["espera"]] == [1, 2]


def test_pedir_lista_de_espera_mesmo_com_vaga(logado):
    van = nova_van(logado, capacidade=5)
    r = colocar(logado, van["id"], novo_passageiro(logado, 0)["id"], lista_de_espera=True).json()
    assert r["situacao"] == "espera" and r["assento"] is None


def test_cadastrar_passageiro_novo_ja_na_van(logado):
    van = nova_van(logado)
    r = logado.post(
        f"/api/veiculos/{van['id']}/reservas",
        json={
            "novo_passageiro": {
                "nome": "Pessoa Nova",
                "documento_tipo": "cpf",
                "documento_numero": "529.982.247-25",
            }
        },
    )
    assert r.status_code == 201 and r.json()["passageiro"]["nome"] == "Pessoa Nova"


def test_exige_passageiro_existente_ou_novo(logado):
    van = nova_van(logado)
    assert logado.post(f"/api/veiculos/{van['id']}/reservas", json={}).status_code == 422


def test_assento_escolhido_e_assento_ocupado(logado):
    van = nova_van(logado, capacidade=4)
    a, b = novo_passageiro(logado, 0), novo_passageiro(logado, 1)
    assert colocar(logado, van["id"], a["id"], assento=3).json()["assento"] == 3
    r = colocar(logado, van["id"], b["id"], assento=3)
    assert r.status_code == 409 and "assento 3" in r.json()["detail"]
    assert colocar(logado, van["id"], b["id"], assento=9).status_code == 409  # além da capacidade


def test_mesma_pessoa_nao_entra_duas_vezes_na_mesma_viagem(logado):
    van1, van2 = nova_van(logado, nome="Van 1"), nova_van(logado, nome="Van 2")
    p = novo_passageiro(logado, 0)
    assert colocar(logado, van1["id"], p["id"]).status_code == 201
    r = colocar(logado, van2["id"], p["id"])
    assert r.status_code == 409 and "Van 1" in r.json()["detail"]


def test_mesma_pessoa_pode_ir_em_viagens_diferentes(logado):
    van1, van2 = nova_van(logado, evento_id=1), nova_van(logado, evento_id=2)
    p = novo_passageiro(logado, 0)
    assert colocar(logado, van1["id"], p["id"]).status_code == 201
    assert colocar(logado, van2["id"], p["id"]).status_code == 201
    assert len(logado.get(f"/api/passageiros/{p['id']}").json()["viagens"]) == 2


def test_cancelar_libera_o_assento(logado):
    van = nova_van(logado, capacidade=1)
    a, b = novo_passageiro(logado, 0), novo_passageiro(logado, 1)
    ra = colocar(logado, van["id"], a["id"]).json()
    assert colocar(logado, van["id"], b["id"]).json()["situacao"] == "espera"
    cancelada = logado.post(f"/api/reservas/{ra['id']}/cancelar").json()
    assert cancelada["situacao"] == "cancelado" and cancelada["assento"] is None
    d = detalhe(logado, van["id"])
    assert d["livres"] == 1 and len(d["canceladas"]) == 1


def test_confirmar_da_espera_quando_abre_vaga(logado):
    van = nova_van(logado, capacidade=1)
    a, b = novo_passageiro(logado, 0), novo_passageiro(logado, 1)
    ra = colocar(logado, van["id"], a["id"]).json()
    rb = colocar(logado, van["id"], b["id"]).json()
    assert logado.post(f"/api/reservas/{rb['id']}/confirmar").status_code == 409  # ainda lotada
    logado.post(f"/api/reservas/{ra['id']}/cancelar")
    promovido = logado.post(f"/api/reservas/{rb['id']}/confirmar").json()
    assert promovido["situacao"] == "confirmado" and promovido["assento"] == 1


def test_mandar_confirmado_para_a_espera_libera_o_assento(logado):
    van = nova_van(logado, capacidade=2)
    r = colocar(logado, van["id"], novo_passageiro(logado, 0)["id"]).json()
    espera = logado.post(f"/api/reservas/{r['id']}/espera").json()
    assert espera["situacao"] == "espera" and espera["assento"] is None
    assert detalhe(logado, van["id"])["livres"] == 2


def test_readicionar_cancelado_reativa_e_mantem_os_pagamentos(logado):
    van = nova_van(logado, valor=10000)
    p = novo_passageiro(logado, 0)
    r = colocar(logado, van["id"], p["id"]).json()
    logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 4000})
    logado.post(f"/api/reservas/{r['id']}/cancelar")
    volta = colocar(logado, van["id"], p["id"]).json()
    assert volta["id"] == r["id"] and volta["situacao"] == "confirmado"
    assert volta["pago_centavos"] == 4000 and volta["status_pagamento"] == "parcial"


def test_trocar_de_assento(logado):
    van = nova_van(logado, capacidade=4)
    r = colocar(logado, van["id"], novo_passageiro(logado, 0)["id"]).json()
    assert logado.patch(f"/api/reservas/{r['id']}", json={"assento": 4}).json()["assento"] == 4
    outro = colocar(logado, van["id"], novo_passageiro(logado, 1)["id"], assento=2).json()
    assert logado.patch(f"/api/reservas/{outro['id']}", json={"assento": 4}).status_code == 409


def test_transferir_para_outra_van_da_mesma_viagem(logado):
    van1, van2 = nova_van(logado, nome="Van 1"), nova_van(logado, nome="Van 2")
    r = colocar(logado, van1["id"], novo_passageiro(logado, 0)["id"]).json()
    nova = logado.post(f"/api/reservas/{r['id']}/transferir", json={"veiculo_id": van2["id"]}).json()
    assert nova["veiculo_id"] == van2["id"] and nova["situacao"] == "confirmado" and nova["assento"] == 1
    assert detalhe(logado, van1["id"])["livres"] == van1["capacidade"]


def test_nao_transfere_para_van_de_outra_viagem(logado):
    van1, van_outra = nova_van(logado, evento_id=1), nova_van(logado, evento_id=2)
    r = colocar(logado, van1["id"], novo_passageiro(logado, 0)["id"]).json()
    assert (
        logado.post(f"/api/reservas/{r['id']}/transferir", json={"veiculo_id": van_outra["id"]}).status_code
        == 409
    )


def test_transferir_para_van_lotada(logado):
    van1, van2 = nova_van(logado, nome="Van 1"), nova_van(logado, nome="Van 2", capacidade=1)
    colocar(logado, van2["id"], novo_passageiro(logado, 1)["id"])
    r = colocar(logado, van1["id"], novo_passageiro(logado, 0)["id"]).json()
    recusa = logado.post(f"/api/reservas/{r['id']}/transferir", json={"veiculo_id": van2["id"]})
    assert recusa.status_code == 409 and "lotada" in recusa.json()["detail"]
    aceita = logado.post(
        f"/api/reservas/{r['id']}/transferir",
        json={"veiculo_id": van2["id"], "entrar_na_espera_se_lotado": True},
    ).json()
    assert aceita["situacao"] == "espera" and aceita["posicao_espera"] == 1


def test_apaga_reserva_sem_pagamento(logado):
    van = nova_van(logado)
    r = colocar(logado, van["id"], novo_passageiro(logado, 0)["id"]).json()
    assert logado.delete(f"/api/reservas/{r['id']}").status_code == 204


# ---------------------------------------------------------------- pagamentos
def reserva_de_100(c, valor=10000):
    van = nova_van(c, valor=valor)
    return colocar(c, van["id"], novo_passageiro(c, 0)["id"]).json()


def test_reserva_nasce_pendente_com_o_valor_da_van(logado):
    r = reserva_de_100(logado)
    assert (
        r["valor_total_centavos"] == 10000
        and r["status_pagamento"] == "pendente"
        and r["saldo_centavos"] == 10000
    )


def test_pagamento_parcial_depois_total(logado):
    r = reserva_de_100(logado)
    parcial = logado.post(
        f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 3000, "data": date.today().isoformat()}
    ).json()
    assert parcial["status_pagamento"] == "parcial" and parcial["saldo_centavos"] == 7000
    assert parcial["pagamentos"][0]["tipo"] == "parcial"
    final = logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 7000}).json()
    assert final["status_pagamento"] == "pago" and final["saldo_centavos"] == 0
    assert final["pagamentos"][1]["tipo"] == "total"


def test_quitar_registra_o_que_falta_na_data_escolhida(logado):
    r = reserva_de_100(logado)
    logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 2500})
    ontem = (date.today() - timedelta(days=1)).isoformat()
    quitada = logado.post(f"/api/reservas/{r['id']}/quitar", json={"data": ontem}).json()
    assert quitada["status_pagamento"] == "pago" and quitada["pago_centavos"] == 10000
    # a lista vem ordenada por data, então o de ontem aparece antes do de hoje
    quitacao = next(p for p in quitada["pagamentos"] if p["tipo"] == "total")
    assert quitacao["valor_centavos"] == 7500 and quitacao["data"] == ontem
    assert quitacao["registrado_por"] == "Equipe Teste"
    assert quitada["ultimo_pagamento"] == date.today().isoformat()  # o mais recente é o parcial de hoje


def test_nao_aceita_pagamento_acima_do_saldo(logado):
    r = reserva_de_100(logado)
    resposta = logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 10001})
    assert resposta.status_code == 409 and "R$ 100,00" in resposta.json()["detail"]


def test_nao_quita_duas_vezes(logado):
    r = reserva_de_100(logado)
    logado.post(f"/api/reservas/{r['id']}/quitar", json={})
    assert logado.post(f"/api/reservas/{r['id']}/quitar", json={}).status_code == 409
    assert logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 100}).status_code == 409


def test_data_de_pagamento_no_futuro_e_recusada(logado):
    r = reserva_de_100(logado)
    amanha = (date.today() + timedelta(days=1)).isoformat()
    assert (
        logado.post(
            f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 100, "data": amanha}
        ).status_code
        == 422
    )


def test_sem_valor_definido_nao_registra_pagamento(logado):
    van = nova_van(logado, valor=0)
    r = colocar(logado, van["id"], novo_passageiro(logado, 0)["id"]).json()
    assert r["status_pagamento"] == "sem_valor"
    assert logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 100}).status_code == 422
    definido = logado.patch(f"/api/reservas/{r['id']}", json={"valor_total_centavos": 8000}).json()
    assert definido["status_pagamento"] == "pendente"


def test_valor_total_nao_fica_abaixo_do_ja_pago(logado):
    r = reserva_de_100(logado)
    logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 6000})
    assert logado.patch(f"/api/reservas/{r['id']}", json={"valor_total_centavos": 5000}).status_code == 409
    assert (
        logado.patch(f"/api/reservas/{r['id']}", json={"valor_total_centavos": 6000}).json()[
            "status_pagamento"
        ]
        == "pago"
    )


def test_desfazer_pagamento_recalcula_o_status(logado):
    r = reserva_de_100(logado)
    feito = logado.post(f"/api/reservas/{r['id']}/quitar", json={}).json()
    assert feito["status_pagamento"] == "pago"
    desfeito = logado.delete(f"/api/pagamentos/{feito['pagamentos'][0]['id']}").json()
    assert desfeito["status_pagamento"] == "pendente" and desfeito["pagamentos"] == []


def test_reserva_cancelada_nao_recebe_pagamento_e_nao_e_apagada_com_historico(logado):
    r = reserva_de_100(logado)
    logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 2000})
    logado.post(f"/api/reservas/{r['id']}/cancelar")
    assert logado.post(f"/api/reservas/{r['id']}/pagamentos", json={"valor_centavos": 100}).status_code == 409
    assert logado.delete(f"/api/reservas/{r['id']}").status_code == 409


def test_quem_esta_na_espera_pode_pagar_adiantado(logado):
    van = nova_van(logado, capacidade=1)
    colocar(logado, van["id"], novo_passageiro(logado, 0)["id"])
    espera = colocar(logado, van["id"], novo_passageiro(logado, 1)["id"]).json()
    pago = logado.post(f"/api/reservas/{espera['id']}/quitar", json={}).json()
    assert pago["situacao"] == "espera" and pago["status_pagamento"] == "pago"


# ---------------------------------------------------------------- painel e totais
def test_totais_do_evento_e_do_painel(logado):
    van = nova_van(logado, capacidade=2, valor=10000)
    a, b, c = (novo_passageiro(logado, i) for i in range(3))
    ra = colocar(logado, van["id"], a["id"]).json()
    colocar(logado, van["id"], b["id"])
    colocar(logado, van["id"], c["id"])  # espera
    logado.post(f"/api/reservas/{ra['id']}/quitar", json={})

    evento = logado.get("/api/eventos/1").json()
    assert (evento["confirmados"], evento["em_espera"], evento["assentos"]) == (2, 1, 2)
    assert evento["pago_centavos"] == 10000 and evento["a_receber_centavos"] == 10000

    painel = logado.get("/api/painel").json()
    assert painel["proximas_viagens"] == 2 and painel["confirmados"] == 2
    assert [p["passageiro"] for p in painel["pendencias"]] == ["Passageiro Numero 1"]
    # o "Show Dois" está a 60 dias, então não entra no alerta de 45 dias sem van
    assert painel["sem_veiculo"] == []


def test_painel_avisa_evento_proximo_sem_van(logado):
    avisos = logado.get("/api/painel").json()["sem_veiculo"]
    assert [e["titulo"] for e in avisos] == ["Show Um"]  # está a 20 dias e ainda não tem van


# ---------------------------------------------------------------- contatos
def test_crud_de_contatos(logado):
    r = logado.post(
        "/api/contatos",
        json={
            "nome": "Viação Estrela",
            "categoria": "empresa_fretamento",
            "empresa": "Estrela LTDA",
            "telefone": "(16) 3333-0000",
            "email": "a@b.com",
        },
    )
    assert r.status_code == 201
    id_ = r.json()["id"]
    assert (
        logado.patch(f"/api/contatos/{id_}", json={"ativo": False, "telefone": None}).json()["ativo"] is False
    )
    assert logado.get("/api/contatos", params={"categoria": "motorista"}).json() == []
    assert logado.get("/api/contatos", params={"q": "estrela"}).json()[0]["nome"] == "Viação Estrela"
    assert logado.get("/api/contatos", params={"somente_ativos": True}).json() == []
    assert logado.delete(f"/api/contatos/{id_}").status_code == 204


def test_contato_em_uso_nao_e_apagado(logado):
    contato = logado.post("/api/contatos", json={"nome": "Seu Raimundo", "categoria": "motorista"}).json()
    nova_van(logado, contato_id=contato["id"])
    r = logado.delete(f"/api/contatos/{contato['id']}")
    assert r.status_code == 409 and "1 van" in r.json()["detail"]


def test_contato_exige_categoria_valida_e_email_valido(logado):
    assert logado.post("/api/contatos", json={"nome": "Fulano", "categoria": "alienigena"}).status_code == 422
    assert (
        logado.post(
            "/api/contatos", json={"nome": "Fulano", "categoria": "outro", "email": "isto-nao-e-email"}
        ).status_code
        == 422
    )
