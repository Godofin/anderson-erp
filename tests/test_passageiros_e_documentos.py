import pytest

from app.services.documentos import (
    cpf_valido,
    formatar_documento,
    mascarar_documento,
    normalizar_documento,
)
from tests.conftest import CPFS, novo_passageiro


@pytest.mark.parametrize("cpf", CPFS)
def test_cpfs_validos(cpf):
    assert cpf_valido(cpf)


@pytest.mark.parametrize("cpf", ["12345678900", "11111111111", "1234567890", "abcdefghijk", ""])
def test_cpfs_invalidos(cpf):
    assert not cpf_valido(cpf)


def test_normaliza_cpf_com_pontuacao():
    assert normalizar_documento("cpf", "529.982.247-25") == "52998224725"


def test_normaliza_rg_com_letra_e_estado():
    assert normalizar_documento("rg", "sp 12.345.678-x") == "SP12345678X"


def test_rg_curto_demais_e_recusado():
    with pytest.raises(ValueError):
        normalizar_documento("rg", "123")


def test_mascara_nao_mostra_o_documento_inteiro():
    assert mascarar_documento("cpf", "52998224725") == "***.***.247-**"
    assert mascarar_documento("rg", "SP12345678X") == "••••••••78X"
    assert formatar_documento("cpf", "52998224725") == "529.982.247-25"


def test_cadastro_com_cpf_formatado(logado):
    r = logado.post(
        "/api/passageiros",
        json={"nome": "  Maria  da Silva ", "documento_tipo": "cpf", "documento_numero": "529.982.247-25"},
    )
    assert r.status_code == 201
    corpo = r.json()
    assert corpo["nome"] == "Maria  da Silva"
    assert corpo["documento_numero"] == "52998224725"
    assert corpo["documento_formatado"] == "529.982.247-25"
    assert corpo["id"] >= 1


def test_cpf_invalido_e_recusado(logado):
    r = logado.post(
        "/api/passageiros",
        json={"nome": "Maria da Silva", "documento_tipo": "cpf", "documento_numero": "123.456.789-00"},
    )
    assert r.status_code == 422
    assert "CPF inválido" in r.text


def test_mesmo_documento_nao_cadastra_duas_vezes(logado):
    primeiro = novo_passageiro(logado, 0, "Maria da Silva")
    r = logado.post(
        "/api/passageiros",
        json={"nome": "Outra Pessoa", "documento_tipo": "cpf", "documento_numero": "52998224725"},
    )
    assert r.status_code == 409
    assert r.json()["detail"]["passageiro_id"] == primeiro["id"]
    assert "Maria da Silva" in r.json()["detail"]["mensagem"]


def test_lista_mostra_documento_mascarado_e_detalhe_mostra_completo(logado):
    p = novo_passageiro(logado, 0, "Maria da Silva")
    linha = logado.get("/api/passageiros").json()[0]
    assert linha["documento_mascarado"] == "***.***.247-**"
    assert "documento_numero" not in linha
    assert logado.get(f"/api/passageiros/{p['id']}").json()["documento_formatado"] == "529.982.247-25"


def test_busca_por_nome_e_por_documento(logado):
    novo_passageiro(logado, 0, "Maria da Silva")
    novo_passageiro(logado, 1, "João Pereira")
    assert [p["nome"] for p in logado.get("/api/passageiros", params={"q": "maria"}).json()] == [
        "Maria da Silva"
    ]
    assert [p["nome"] for p in logado.get("/api/passageiros", params={"q": "444.777"}).json()] == [
        "João Pereira"
    ]


def test_editar_documento_para_um_que_ja_existe_e_recusado(logado):
    novo_passageiro(logado, 0)
    segundo = novo_passageiro(logado, 1)
    r = logado.patch(
        f"/api/passageiros/{segundo['id']}", json={"documento_tipo": "cpf", "documento_numero": CPFS[0]}
    )
    assert r.status_code == 409


def test_editar_exige_tipo_e_numero_juntos(logado):
    p = novo_passageiro(logado, 0)
    assert logado.patch(f"/api/passageiros/{p['id']}", json={"documento_tipo": "rg"}).status_code == 422


def test_nao_apaga_passageiro_com_viagem(logado):
    from tests.conftest import colocar, nova_van

    p = novo_passageiro(logado, 0)
    van = nova_van(logado)
    assert colocar(logado, van["id"], p["id"]).status_code == 201
    r = logado.delete(f"/api/passageiros/{p['id']}")
    assert r.status_code == 409


def test_apaga_passageiro_sem_viagem(logado):
    p = novo_passageiro(logado, 0)
    assert logado.delete(f"/api/passageiros/{p['id']}").status_code == 204
    assert logado.get(f"/api/passageiros/{p['id']}").status_code == 404
