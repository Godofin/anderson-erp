"""Tabelas do ERP. Todas começam com erp_ para conviver com as tabelas da API pública."""

from datetime import UTC, date, datetime

from sqlmodel import Field, SQLModel, UniqueConstraint


def agora() -> datetime:
    """Momento atual em UTC, com fuso. O SQLModel guarda em UTC e devolve com fuso nos dois bancos."""
    return datetime.now(UTC)


class Usuario(SQLModel, table=True):
    __tablename__ = "erp_usuarios"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(max_length=200, unique=True, index=True)
    nome: str = Field(max_length=120)
    senha_hash: str
    ativo: bool = True
    criado_em: datetime = Field(default_factory=agora)


class Contato(SQLModel, table=True):
    """Pessoas e empresas de apoio: motoristas, empresas de fretamento, guias, fornecedores."""

    __tablename__ = "erp_contatos"

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(max_length=120, index=True)
    categoria: str = Field(max_length=30, index=True)
    empresa: str | None = Field(default=None, max_length=120)
    telefone: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=200)
    observacoes: str | None = Field(default=None, max_length=1000)
    ativo: bool = True
    criado_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)


class Passageiro(SQLModel, table=True):
    """Cadastro único de passageiros. O documento é CPF ou RG, normalizado."""

    __tablename__ = "erp_passageiros"
    __table_args__ = (UniqueConstraint("documento_tipo", "documento_numero", name="uq_passageiro_documento"),)

    id: int | None = Field(default=None, primary_key=True)
    nome: str = Field(max_length=120, index=True)
    documento_tipo: str = Field(max_length=3)
    documento_numero: str = Field(max_length=20, index=True)
    criado_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)


class Veiculo(SQLModel, table=True):
    """Uma van, micro-ônibus ou ônibus de uma viagem. evento_id é o id do evento na API pública."""

    __tablename__ = "erp_veiculos"

    id: int | None = Field(default=None, primary_key=True)
    evento_id: int = Field(index=True)
    nome: str = Field(max_length=60)
    tipo: str = Field(max_length=20)
    placa: str | None = Field(default=None, max_length=10)
    capacidade: int
    valor_padrao_centavos: int = 0
    contato_id: int | None = Field(default=None, foreign_key="erp_contatos.id")
    observacoes: str | None = Field(default=None, max_length=1000)
    criado_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)


class Reserva(SQLModel, table=True):
    """A vaga de um passageiro numa viagem: confirmada, na lista de espera ou cancelada."""

    __tablename__ = "erp_reservas"
    __table_args__ = (
        UniqueConstraint("evento_id", "passageiro_id", name="uq_reserva_evento_passageiro"),
        UniqueConstraint("veiculo_id", "assento", name="uq_reserva_veiculo_assento"),
    )

    id: int | None = Field(default=None, primary_key=True)
    veiculo_id: int = Field(foreign_key="erp_veiculos.id", index=True)
    evento_id: int = Field(index=True)
    passageiro_id: int = Field(foreign_key="erp_passageiros.id", index=True)
    situacao: str = Field(max_length=12, index=True)
    assento: int | None = None
    entrou_na_espera_em: datetime | None = None
    cidade_embarque: str | None = Field(default=None, max_length=80)
    valor_total_centavos: int = 0
    observacoes: str | None = Field(default=None, max_length=500)
    criado_em: datetime = Field(default_factory=agora)
    atualizado_em: datetime = Field(default_factory=agora)


class Pagamento(SQLModel, table=True):
    """Cada pagamento recebido. O status (pendente, parcial, pago) é calculado, não guardado."""

    __tablename__ = "erp_pagamentos"

    id: int | None = Field(default=None, primary_key=True)
    reserva_id: int = Field(foreign_key="erp_reservas.id", index=True)
    data: date
    valor_centavos: int
    tipo: str = Field(max_length=7)
    observacao: str | None = Field(default=None, max_length=300)
    registrado_por: str = Field(max_length=120)
    criado_em: datetime = Field(default_factory=agora)
