"""Comandos de apoio.

python -m app.cli criar-usuario --email maria@exemplo.com --nome "Maria"
python -m app.cli dados-demo        (só em desenvolvimento)
"""

import argparse
import getpass
import os
import random
import sys
from datetime import date, timedelta

from email_validator import EmailNotValidError, validate_email
from sqlmodel import Session, select

from app.api_publica import ApiPublicaIndisponivel
from app.config import get_settings
from app.db import criar_tabelas, engine
from app.eventos_publicos import obter_eventos
from app.models import Contato, Passageiro, Usuario, Veiculo
from app.schemas import PagamentoEntrada, PassageiroEntrada, QuitacaoEntrada, ReservaEntrada
from app.security import gerar_hash
from app.services import reservas as regras


def criar_usuario(args: argparse.Namespace) -> int:
    criar_tabelas()
    senha = os.environ.get("ERP_NOVA_SENHA")
    if not senha:
        senha = getpass.getpass("Senha (mínimo 10 caracteres): ")
        if senha != getpass.getpass("Repita a senha: "):
            print("As senhas não conferem.", file=sys.stderr)
            return 1
    if len(senha) < 10:
        print("A senha precisa ter pelo menos 10 caracteres.", file=sys.stderr)
        return 1
    email = args.email.strip().lower()
    try:
        email = validate_email(email, check_deliverability=False).normalized
    except EmailNotValidError as erro:
        print(f"E-mail inválido: {erro}", file=sys.stderr)
        return 1
    with Session(engine) as session:
        existente = session.exec(select(Usuario).where(Usuario.email == email)).first()
        if existente:
            existente.senha_hash = gerar_hash(senha)
            existente.nome = args.nome
            existente.ativo = True
            session.add(existente)
            acao = "atualizado"
        else:
            session.add(Usuario(email=email, nome=args.nome, senha_hash=gerar_hash(senha)))
            acao = "criado"
        session.commit()
    print(f"Usuário {email} {acao}.")
    return 0


def _cpf_ficticio(base: int) -> str:
    """CPF com dígitos verificadores válidos, gerado a partir de um número (só para a demonstração)."""
    digitos = [int(c) for c in f"{base:09d}"]
    for tamanho in (9, 10):
        soma = sum(digitos[i] * (tamanho + 1 - i) for i in range(tamanho))
        digitos.append((soma * 10) % 11 % 10)
    return "".join(map(str, digitos))


NOMES = [
    "Ana Beatriz Ferreira", "Bruno Henrique Costa", "Camila Rodrigues Lima", "Diego Almeida Santos",
    "Eduarda Martins Rocha", "Felipe Augusto Barbosa", "Gabriela Nunes Teixeira", "Heitor Gomes Ribeiro",
    "Isabela Carvalho Dias", "João Pedro Moreira", "Karina Souza Pinto", "Lucas Oliveira Cardoso",
    "Mariana Azevedo Freitas", "Nicolas Batista Araújo", "Olívia Castro Mendes", "Paulo Ricardo Campos",
    "Quézia Monteiro Lopes", "Rafael Duarte Correia", "Sabrina Vieira Machado", "Thiago Fernandes Melo",
    "Ursula Cavalcante Reis", "Vitor Hugo Andrade", "Yasmin Tavares Nogueira", "Zeca Antunes Barros",
]  # fmt: skip


def dados_demo(_: argparse.Namespace) -> int:
    if get_settings().ambiente != "dev":
        print("Os dados de demonstração só podem ser criados com ERP_AMBIENTE=dev.", file=sys.stderr)
        return 1
    criar_tabelas()
    try:
        hoje = date.today()
        eventos = [e for e in obter_eventos() if e.ativo and e.data_inicio and e.data_inicio >= hoje]
    except ApiPublicaIndisponivel:
        print("Não consegui ler os eventos da API pública.", file=sys.stderr)
        return 1
    eventos.sort(key=lambda e: e.data_inicio)
    if len(eventos) < 2:
        print("Preciso de pelo menos 2 eventos futuros na API pública.", file=sys.stderr)
        return 1

    aleatorio = random.Random(42)
    with Session(engine) as session:
        if session.exec(select(Veiculo)).first():
            print("Já existem vans cadastradas. Apague o arquivo erp.db para recomeçar.", file=sys.stderr)
            return 1

        motoristas = [
            Contato(nome="Seu Raimundo (exemplo)", categoria="motorista", telefone="(16) 99999-0001", observacoes="Dado de demonstração."),
            Contato(nome="Viação Estrela do Sul (exemplo)", categoria="empresa_fretamento", empresa="Viação Estrela do Sul", telefone="(16) 3333-0002", email="contato@exemplo.com.br", observacoes="Dado de demonstração."),
            Contato(nome="Carla Guia (exemplo)", categoria="guia", telefone="(16) 99999-0003", observacoes="Dado de demonstração."),
        ]  # fmt: skip
        session.add_all(motoristas)
        session.flush()

        passageiros = []
        for i, nome in enumerate(NOMES):
            if i % 4 == 3:
                dados = PassageiroEntrada(
                    nome=nome,
                    documento_tipo="rg",
                    documento_numero=f"{30 + i}.{100 + i * 7}.{200 + i * 3}-{i % 10}",
                )
            else:
                dados = PassageiroEntrada(
                    nome=nome,
                    documento_tipo="cpf",
                    documento_numero=_cpf_ficticio(100_000_000 + i * 7_919_113),
                )
            passageiro = Passageiro(**dados.model_dump())
            session.add(passageiro)
            passageiros.append(passageiro)
        session.flush()

        def van(evento, nome, tipo, assentos, valor, contato):
            veiculo = Veiculo(
                evento_id=evento.id,
                nome=nome,
                tipo=tipo,
                capacidade=assentos,
                valor_padrao_centavos=valor,
                contato_id=contato.id,
            )
            session.add(veiculo)
            session.flush()
            return veiculo

        van1 = van(eventos[0], "Van 1", "van", 15, 15000, motoristas[0])
        van2 = van(eventos[0], "Ônibus 1", "onibus", 6, 12000, motoristas[1])
        van3 = van(eventos[1], "Van 1", "van", 15, 11000, motoristas[0])

        def colocar(veiculo, passageiro, **extra):
            reserva = regras.adicionar_reserva(
                session, veiculo.id, ReservaEntrada(passageiro_id=passageiro.id, **extra)
            )
            return reserva

        reservas = []
        for p in passageiros[:12]:
            reservas.append(
                colocar(van1, p, cidade_embarque=aleatorio.choice(eventos[0].cidades or ["Araraquara"]))
            )
        for p in passageiros[12:20]:  # 8 pessoas em 6 assentos: 2 vão para a lista de espera
            reservas.append(
                colocar(van2, p, cidade_embarque=aleatorio.choice(eventos[0].cidades or ["Araraquara"]))
            )
        for p in passageiros[:5]:  # mesmas pessoas em outra viagem
            reservas.append(colocar(van3, p))

        for i, reserva in enumerate(reservas):
            if reserva.situacao != "confirmado":
                continue
            data = hoje - timedelta(days=aleatorio.randint(1, 20))
            if i % 3 == 0:
                regras.quitar(session, reserva, QuitacaoEntrada(data=data), "Demonstração")
            elif i % 3 == 1:
                regras.registrar_pagamento(
                    session,
                    reserva,
                    PagamentoEntrada(data=data, valor_centavos=reserva.valor_total_centavos // 2),
                    "Demonstração",
                )
        session.commit()
    print(f"Dados de demonstração criados para: {eventos[0].titulo} e {eventos[1].titulo}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="comando", required=True)
    u = sub.add_parser("criar-usuario", help="cria (ou troca a senha de) um usuário do ERP")
    u.add_argument("--email", required=True)
    u.add_argument("--nome", required=True)
    u.set_defaults(func=criar_usuario)
    d = sub.add_parser("dados-demo", help="preenche o banco local com dados de exemplo")
    d.set_defaults(func=dados_demo)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
