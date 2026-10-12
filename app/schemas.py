"""Contratos da API (o que entra e o que sai). Sem Ellipsis e sem RootModel, como pede a skill."""

from datetime import date, datetime
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator

from app.services.documentos import normalizar_documento

TipoVeiculo = Literal["van", "micro_onibus", "onibus"]
CategoriaContato = Literal["motorista", "empresa_fretamento", "guia", "fornecedor", "outro"]
TipoDocumento = Literal["cpf", "rg"]
Situacao = Literal["confirmado", "espera", "cancelado"]
StatusPagamento = Literal["sem_valor", "pendente", "parcial", "pago"]

Nome = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
TextoCurto = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Observacao = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Centavos = Annotated[int, Field(ge=0, le=100_000_00)]


# ---------------------------------------------------------------- auth
class LoginEntrada(BaseModel):
    # No login o e-mail é só um texto: quem já tem conta nunca fica trancado para fora por causa do formato.
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    senha: Annotated[str, Field(min_length=1, max_length=200)]


class UsuarioPublico(BaseModel):
    id: int
    email: str
    nome: str


# ---------------------------------------------------------------- contatos
class ContatoEntrada(BaseModel):
    nome: Nome
    categoria: CategoriaContato
    empresa: TextoCurto | None = None
    telefone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    email: EmailStr | None = None
    observacoes: Observacao | None = None
    ativo: bool = True


class ContatoAtualizacao(BaseModel):
    nome: Nome | None = None
    categoria: CategoriaContato | None = None
    empresa: TextoCurto | None = None
    telefone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None
    email: EmailStr | None = None
    observacoes: Observacao | None = None
    ativo: bool | None = None


class ContatoPublico(BaseModel):
    id: int
    nome: str
    categoria: CategoriaContato
    empresa: str | None
    telefone: str | None
    email: str | None
    observacoes: str | None
    ativo: bool
    veiculos: int = 0


# ---------------------------------------------------------------- passageiros
class PassageiroEntrada(BaseModel):
    nome: Nome
    documento_tipo: TipoDocumento
    documento_numero: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]

    @model_validator(mode="after")
    def validar_documento(self) -> Self:
        self.documento_numero = normalizar_documento(self.documento_tipo, self.documento_numero)
        return self


class PassageiroAtualizacao(BaseModel):
    nome: Nome | None = None
    documento_tipo: TipoDocumento | None = None
    documento_numero: Annotated[str, StringConstraints(strip_whitespace=True, max_length=30)] | None = None

    @model_validator(mode="after")
    def validar_documento(self) -> Self:
        if (self.documento_tipo is None) != (self.documento_numero is None):
            raise ValueError("Informe o tipo e o número do documento juntos.")
        if self.documento_tipo and self.documento_numero:
            self.documento_numero = normalizar_documento(self.documento_tipo, self.documento_numero)
        return self


class PassageiroResumo(BaseModel):
    """Versão de lista: o documento aparece mascarado."""

    id: int
    nome: str
    documento_tipo: TipoDocumento
    documento_mascarado: str


class PassageiroLinha(PassageiroResumo):
    """Linha da lista de passageiros, com quantas viagens a pessoa já tem."""

    viagens: int


class HistoricoViagem(BaseModel):
    reserva_id: int
    evento_id: int
    evento_titulo: str | None
    veiculo_id: int
    veiculo_nome: str
    situacao: Situacao
    status_pagamento: StatusPagamento
    saldo_centavos: int


class PassageiroDetalhe(PassageiroResumo):
    """Versão de detalhe: documento completo. Só quem está logado chega aqui."""

    documento_numero: str
    documento_formatado: str
    viagens: list[HistoricoViagem]


# ---------------------------------------------------------------- veículos
class VeiculoEntrada(BaseModel):
    evento_id: Annotated[int, Field(ge=1)]
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
    tipo: TipoVeiculo
    placa: Annotated[str, StringConstraints(strip_whitespace=True, max_length=10)] | None = None
    capacidade: Annotated[int, Field(ge=1, le=80)]
    valor_padrao_centavos: Centavos = 0
    contato_id: int | None = None
    observacoes: Observacao | None = None


class VeiculoAtualizacao(BaseModel):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] | None = None
    tipo: TipoVeiculo | None = None
    placa: Annotated[str, StringConstraints(strip_whitespace=True, max_length=10)] | None = None
    capacidade: Annotated[int, Field(ge=1, le=80)] | None = None
    valor_padrao_centavos: Centavos | None = None
    contato_id: int | None = None
    observacoes: Observacao | None = None


class ContatoMini(BaseModel):
    id: int
    nome: str
    telefone: str | None
    categoria: CategoriaContato


class VeiculoResumo(BaseModel):
    id: int
    evento_id: int
    nome: str
    tipo: TipoVeiculo
    placa: str | None
    capacidade: int
    confirmados: int
    livres: int
    em_espera: int
    pago_centavos: int
    a_receber_centavos: int
    contato: ContatoMini | None
    fechada: bool = False
    fechada_em: datetime | None = None


# ---------------------------------------------------------------- reservas e pagamentos
class PagamentoPublico(BaseModel):
    id: int
    data: date
    valor_centavos: int
    tipo: Literal["parcial", "total"]
    observacao: str | None
    registrado_por: str


class ReservaPublica(BaseModel):
    id: int
    veiculo_id: int
    evento_id: int
    passageiro: PassageiroResumo
    situacao: Situacao
    assento: int | None
    posicao_espera: int | None
    cidade_embarque: str | None
    valor_total_centavos: int
    pago_centavos: int
    saldo_centavos: int
    status_pagamento: StatusPagamento
    ultimo_pagamento: date | None
    observacoes: str | None
    pagamentos: list[PagamentoPublico]


class VeiculoDetalhe(VeiculoResumo):
    valor_padrao_centavos: int
    observacoes: str | None
    confirmadas: list[ReservaPublica]
    espera: list[ReservaPublica]
    canceladas: list[ReservaPublica]


class ReservaEntrada(BaseModel):
    """Coloca um passageiro numa van. Informe passageiro_id OU novo_passageiro."""

    passageiro_id: int | None = None
    novo_passageiro: PassageiroEntrada | None = None
    lista_de_espera: bool = False
    assento: Annotated[int, Field(ge=1, le=80)] | None = None
    cidade_embarque: TextoCurto | None = None
    valor_total_centavos: Centavos | None = None
    observacoes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @model_validator(mode="after")
    def exigir_um_passageiro(self) -> Self:
        if (self.passageiro_id is None) == (self.novo_passageiro is None):
            raise ValueError("Informe um passageiro existente ou os dados de um novo.")
        return self


class ReservaAtualizacao(BaseModel):
    assento: Annotated[int, Field(ge=1, le=80)] | None = None
    cidade_embarque: TextoCurto | None = None
    valor_total_centavos: Centavos | None = None
    observacoes: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class TransferenciaEntrada(BaseModel):
    veiculo_id: Annotated[int, Field(ge=1)]
    entrar_na_espera_se_lotado: bool = False


class PagamentoEntrada(BaseModel):
    data: date | None = None
    valor_centavos: Annotated[int, Field(ge=1, le=100_000_00)]
    observacao: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


class QuitacaoEntrada(BaseModel):
    data: date | None = None
    observacao: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None


# ---------------------------------------------------------------- eventos e painel
class EventoResumo(BaseModel):
    id: int
    titulo: str
    data_texto: str
    data_inicio: date | None
    data_fim: date | None
    imagem: str | None
    ativo: bool
    destaque: bool
    tipo: Literal["show", "eco"]
    cidades: list[str]
    veiculos: int
    assentos: int
    confirmados: int
    em_espera: int
    pago_centavos: int
    a_receber_centavos: int


class EventoDetalhe(EventoResumo):
    lista_de_veiculos: list[VeiculoResumo]


class PendenciaPainel(BaseModel):
    reserva_id: int
    veiculo_id: int
    passageiro: str
    evento_titulo: str | None
    saldo_centavos: int
    status_pagamento: StatusPagamento


class PainelResposta(BaseModel):
    gerado_em: datetime
    proximas_viagens: int
    assentos: int
    confirmados: int
    em_espera: int
    pago_centavos: int
    a_receber_centavos: int
    sem_veiculo: list[EventoResumo]
    proximos: list[EventoResumo]
    pendencias: list[PendenciaPainel]


# ---------------------------------------------------------------- evento do site (painel admin)
TipoEvento = Literal["show", "eco"]
DestinoBotao = Literal["whatsapp", "link"]


def _endereco_web(valor: str, *, permitir_relativo: bool = False) -> str:
    """Aceita http(s) (e, se permitido, caminhos como bts.html). Recusa javascript: e afins."""
    valor = valor.strip()
    partes = urlparse(valor)
    if partes.scheme in {"http", "https"} and partes.netloc:
        return valor
    if permitir_relativo and not partes.scheme and not partes.netloc and " " not in valor:
        return valor
    raise ValueError(
        "Informe um endereço completo, começando com https://"
        if not permitir_relativo
        else "Informe um endereço completo (https://...) ou o nome de uma página, como bts.html."
    )


class EventoSiteEntrada(BaseModel):
    """Os mesmos campos do formulário de cadastro atual, em português."""

    titulo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    tipo: TipoEvento = "show"
    imagem: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
    descricao: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=6000)]
    data_texto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)]
    data_evento: date
    texto_botao: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)] = (
        "Reservar agora"
    )
    destino_botao: DestinoBotao = "whatsapp"
    link_botao: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    cidades: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]] = []
    saiba_mais_link: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    ativo: bool = False
    destaque: bool = False

    @model_validator(mode="after")
    def conferir(self) -> Self:
        self.imagem = _endereco_web(self.imagem)
        if self.destino_botao == "link":
            if not self.link_botao:
                raise ValueError("Informe o link do botão de reserva.")
            self.link_botao = _endereco_web(self.link_botao)
        else:
            self.link_botao = None
        self.saiba_mais_link = (
            _endereco_web(self.saiba_mais_link, permitir_relativo=True) if self.saiba_mais_link else None
        )
        unicas: list[str] = []
        for cidade in self.cidades:
            if cidade not in unicas:
                unicas.append(cidade)
        self.cidades = unicas
        return self


class EventoSiteFicha(BaseModel):
    """O evento como está no site, para preencher o formulário de edição.

    Não repete as validações da entrada: um evento antigo com dados fora do padrão precisa abrir.
    """

    id: int
    titulo: str
    tipo: TipoEvento
    imagem: str
    descricao: str
    data_texto: str
    data_evento: date | None
    texto_botao: str
    destino_botao: DestinoBotao
    link_botao: str | None
    cidades: list[str]
    saiba_mais_link: str | None
    ativo: bool
    destaque: bool
    veiculos: int
    link_whatsapp: str


class VisibilidadeEntrada(BaseModel):
    ativo: bool


# ---------------------------------------------------------------- linktree
class LinkEntrada(BaseModel):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    imagem_url: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = None
    whatsapp_url: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    data_evento: date | None = None
    ativo: bool = True
    destaque: bool = False

    @model_validator(mode="after")
    def conferir(self) -> Self:
        self.whatsapp_url = _endereco_web(self.whatsapp_url)
        self.imagem_url = _endereco_web(self.imagem_url) if self.imagem_url else None
        return self


class LinkPublico(LinkEntrada):
    id: int


# ---------------------------------------------------------------- van fechada e lista de presença
class PontoEntrada(BaseModel):
    nome: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class PresencaEntrada(BaseModel):
    presente: bool


class PontoPublico(BaseModel):
    id: int
    nome: str
    ordem: int
    presentes: int
    total: int


class PassageiroDaLista(ReservaPublica):
    """Passageiro confirmado da van fechada, com os pontos em que já foi marcado."""

    presente_em: list[int]


class ListaDaViagem(BaseModel):
    veiculo: VeiculoResumo
    fechada_em: datetime
    fechada_por: str
    pontos: list[PontoPublico]
    passageiros: list[PassageiroDaLista]
    fora_da_lista: int
