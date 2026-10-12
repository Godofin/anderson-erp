import os
import tempfile
from datetime import date, timedelta

# O banco de teste é um arquivo temporário. Precisa ser definido antes de importar o app.
_PASTA = tempfile.mkdtemp(prefix="erp-teste-")
os.environ["ERP_DATABASE_URL"] = f"sqlite:///{_PASTA}/teste.db"
os.environ["ERP_SECRET_KEY"] = "chave-usada-somente-nos-testes-0123456789"
os.environ["ERP_AMBIENTE"] = "dev"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

from app import api_publica, eventos_publicos  # noqa: E402
from app.db import criar_tabelas, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402
from app.security import gerar_hash, limitador  # noqa: E402

SENHA = "senha-de-teste-123"
CPFS = ["52998224725", "11144477735", "39053344705", "16899535009", "71428793860", "86288366757"]


def _evento(id_: int, titulo: str, dias: int, ativo: bool = True, cidades=None) -> dict:
    dia = date.today() + timedelta(days=dias)
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
             "setembro", "outubro", "novembro", "dezembro"]  # fmt: skip
    return {
        "id": id_,
        "title": f"Excursão {titulo}",
        "eventName": titulo,
        "date": f"{dia.day} de {meses[dia.month - 1]} de {dia.year} - São Paulo",
        "date_event": dia.isoformat(),
        "year": str(dia.year),
        "image": "https://exemplo.com/a.jpg",
        "alt": "Shows/Eventos",
        "cities": cidades or ["Araraqura", "São Carlos"],
        "active_event": ativo,
        "destaque": id_ == 1,
    }


EVENTOS_FALSOS = [
    _evento(1, "Show Um", 20),
    _evento(2, "Show Dois", 60),
    _evento(3, "Show Passado", -30),
    _evento(4, "Show Desativado", 40, ativo=False),
]


class ApiFalsa:
    """Faz o papel da API pública do site. Guarda o que o ERP enviou, para os testes conferirem."""

    def __init__(self):
        self.eventos = [dict(e) for e in EVENTOS_FALSOS]
        self.links = [
            {"id": 1, "name": "Grupo Show Um", "image_url": None,
             "whatsapp_url": "https://chat.whatsapp.com/abc", "event_date": None,
             "active": True, "destaque": False},
        ]  # fmt: skip
        self.chamadas: list[tuple[str, str, dict | None]] = []
        self.fora_do_ar = False
        self.recusar_com: tuple[int, str] | None = None

    def _resposta(self, codigo, dados=None, metodo="GET", caminho="/"):
        pedido = httpx.Request(metodo, f"http://api-falsa{caminho}")
        if dados is None:
            return httpx.Response(codigo, request=pedido)
        return httpx.Response(codigo, json=dados, request=pedido)

    def __call__(self, metodo, url, json=None, timeout=None, **_):
        caminho = url.split("api-publica-falsa", 1)[-1] if "api-publica-falsa" in url else url
        caminho = "/" + caminho.split("/api/v1/", 1)[-1] if "/api/v1/" in caminho else caminho
        self.chamadas.append((metodo, caminho, json))
        if self.fora_do_ar:
            raise httpx.ConnectError("sem rede")
        if metodo != "GET" and self.recusar_com:
            codigo, detalhe = self.recusar_com
            return self._resposta(codigo, {"detail": detalhe}, metodo, caminho)
        resposta = self._rota(metodo, caminho, json)
        return (
            resposta
            if resposta is not None
            else self._resposta(404, {"detail": "Not found"}, metodo, caminho)
        )

    def _rota(self, metodo, caminho, corpo):
        partes = [p for p in caminho.split("/") if p]
        itens = self.eventos if partes[0] == "events" else self.links
        if partes[0] not in ("events", "linktree"):
            return None
        if metodo == "GET" and len(partes) == 2 and partes[1] == "all":
            return self._resposta(200, itens)
        if metodo == "POST" and len(partes) == 1:
            novo = {**corpo, "id": max([i["id"] for i in itens], default=0) + 1}
            itens.append(novo)
            return self._resposta(201, novo)
        if len(partes) == 2 and partes[1].isdigit():
            alvo = next((i for i in itens if i["id"] == int(partes[1])), None)
            if alvo is None:
                return self._resposta(404, {"detail": "Not found"})
            if metodo == "PUT":
                alvo.update(corpo)
                return self._resposta(200, alvo)
            if metodo == "DELETE":
                itens.remove(alvo)
                return self._resposta(204)
        return None


@pytest.fixture
def api(monkeypatch):
    falsa = ApiFalsa()
    monkeypatch.setattr(api_publica.httpx, "request", falsa)
    monkeypatch.setenv("ERP_API_PUBLICA", "http://api-publica-falsa/api/v1")
    from app.config import get_settings

    get_settings.cache_clear()
    yield falsa
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def ambiente_limpo(api):
    SQLModel.metadata.drop_all(engine)
    criar_tabelas()
    eventos_publicos.limpar_cache()
    limitador._falhas.clear()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def usuario():
    with Session(engine) as s:
        s.add(Usuario(email="equipe@exemplo.com", nome="Equipe Teste", senha_hash=gerar_hash(SENHA)))
        s.commit()


@pytest.fixture
def logado(client, usuario):
    r = client.post("/api/auth/login", json={"email": "equipe@exemplo.com", "senha": SENHA})
    assert r.status_code == 200, r.text
    return client


# ---------- atalhos usados em vários testes ----------
def nova_van(c, evento_id=1, capacidade=3, valor=10000, nome="Van 1", **extra) -> dict:
    r = c.post(
        "/api/veiculos",
        json={"evento_id": evento_id, "nome": nome, "tipo": "van", "capacidade": capacidade,
              "valor_padrao_centavos": valor, **extra},
    )  # fmt: skip
    assert r.status_code == 201, r.text
    return r.json()


def novo_passageiro(c, i=0, nome=None) -> dict:
    r = c.post(
        "/api/passageiros",
        json={"nome": nome or f"Passageiro Numero {i}", "documento_tipo": "cpf", "documento_numero": CPFS[i]},
    )
    assert r.status_code == 201, r.text
    return r.json()


def colocar(c, veiculo_id, passageiro_id, **extra):
    return c.post(f"/api/veiculos/{veiculo_id}/reservas", json={"passageiro_id": passageiro_id, **extra})
