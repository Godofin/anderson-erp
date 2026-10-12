# ERP Anderson Viagem e Turismo

Sistema interno para organizar as viagens: **vans e ônibus por evento, passageiros, lista de espera,
pagamentos e contatos**. Só a equipe acessa (login obrigatório).

## Como ele se encaixa no que já existe

```
Formulário de cadastro ─┐
                        ├──▶ API pública (anderson-api-v1) ──▶ Site (landing page)
ERP (este projeto) ─────┘      mesmas rotas /events e /linktree
        │
        └──▶ tabelas próprias erp_* (vans, passageiros, pagamentos, contatos)
```

- **A API pública e o site não mudam.** O ERP usa as **mesmas rotas que o painel admin atual já usa**
  (`/events` e `/linktree`), então nada na API foi alterado. Eventos cadastrados pelo painel antigo aparecem
  no ERP sozinhos (em até 1 minuto) e os cadastrados pelo ERP aparecem no site, como sempre.
- **Se a API do site cair, o ERP avisa e não salva nada pela metade.** Vans e passageiros continuam funcionando
  com a última cópia dos eventos.
- **Evento novo nasce fora do site.** Você só liga o “Mostrar no site” quando quiser publicar.
- Os dados do ERP ficam em tabelas com prefixo `erp_` (podem ficar no mesmo banco Neon, sem se misturar).
- O ERP é um **serviço separado**, com deploy próprio. Se ele cair, o site continua normal.

## O que dá para fazer

| Tela | Para quê |
| --- | --- |
| **Painel** | Próximas viagens, assentos ocupados, lista de espera, quanto falta receber, alerta de viagem sem van |
| **Eventos e vans** | **Criar, editar, publicar, tirar do site e apagar** eventos (o painel admin) e, dentro de cada um, cadastrar vans/ônibus com a quantidade de assentos |
| **Linktree do site** | Links dos grupos de WhatsApp: criar, editar, esconder e apagar |
| **Van** | Mapa de assentos, passageiros, **lista de espera**, pagamentos (parcial ou completo, com data), transferência entre vans |
| **Passageiros** | Cadastro único: nome, **ID** (`P-00012`) e **documento (CPF ou RG)** |
| **Contatos** | Motoristas, empresas de fretamento, guias e fornecedores; podem ser ligados a cada van |

### Regras que o sistema aplica

- **Van lotada → lista de espera.** Quem entra com a van cheia vai para a fila, na ordem de chegada.
  Quando abre vaga, você confirma o primeiro da fila com um clique.
- **Pagamento calculado.** Pendente, parcial ou pago vem da soma dos pagamentos. “Quitar” registra o que falta,
  na data que você escolher. Não aceita pagamento acima do saldo nem com data no futuro.
- **Cancelar não apaga o histórico.** O assento é liberado, mas os pagamentos continuam registrados. Ao adicionar
  a pessoa de novo na mesma viagem, a reserva é reativada com o que já foi pago.
- **Uma pessoa por viagem.** O mesmo passageiro não entra em duas vans do mesmo evento.
- **CPF validado** (dígitos verificadores). RG aceita letras e a sigla do estado. O documento não se repete.
- **Documento mascarado nas listas** (`***.***.247-**`); completo só na ficha da pessoa.

## Rodar no seu computador

Precisa de Python 3.11+.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"        # Windows (Git Bash)
cp .env.example .env                                  # ajuste se quiser

# cria o primeiro usuário (pede a senha, mínimo 10 caracteres)
.venv/Scripts/python -m app.cli criar-usuario --email voce@empresa.com --nome "Seu Nome"

# opcional: preenche o banco local com vans e passageiros de exemplo (usa os eventos reais do site)
.venv/Scripts/python -m app.cli dados-demo

# sobe o servidor
.venv/Scripts/fastapi dev
```

Abra `http://127.0.0.1:8000`. A documentação interativa da API fica em `/docs` (só em desenvolvimento).

Testes e qualidade de código:

```bash
.venv/Scripts/python -m pytest        # 99 testes (a API do site é simulada nos testes)
.venv/Scripts/python -m ruff check .  # lint
```

## Testar com os dados de verdade

- **Eventos e Linktree** já são os de verdade: o ERP lê e grava na API real do site. Cuidado: apagar ou
  publicar aqui altera o site de verdade. Para treinar, cadastre um evento e deixe “Mostrar no site” desligado.
- **Vans, passageiros, pagamentos e contatos** ficam nas tabelas `erp_*`. Localmente vão para um arquivo SQLite
  (`erp.db`). Para usar o mesmo banco Postgres do Neon, coloque no `.env` (nunca no Git):

```
ERP_DATABASE_URL=postgresql://usuario:senha@host/banco?sslmode=require
```

  Ao subir, o ERP cria só as tabelas `erp_*`; não mexe nas tabelas da API. Não rode `dados-demo` nesse banco.
- Outras opções do `.env`: `ERP_WHATSAPP_NUMERO` (número dos botões “Reservar”, só dígitos com 55) e
  `ERP_API_PUBLICA` (endereço da API do site).

## Segurança

- **Login obrigatório** em tudo que é dado. Senha com **Argon2**; sessão em cookie **HttpOnly**, `SameSite=Strict`
  e `Secure` em produção. Mensagem de erro igual para e-mail inexistente e senha errada.
- **Bloqueio de tentativas**: 5 erros em 15 minutos por e-mail e endereço. Fica em memória, então na Vercel
  (várias instâncias) é uma barreira parcial; a senha forte continua sendo a defesa principal.
- **Contra CSRF**: cookie `SameSite=Strict` e checagem de origem em todo pedido que altera dados.
- **Cabeçalhos**: Content-Security-Policy restritiva (sem scripts ou estilos inline), `X-Robots-Tag: noindex`,
  `nosniff`. O painel também tem `robots.txt` bloqueando tudo.
- **Produção recusa chave fraca**: com `ERP_AMBIENTE=prod`, o app não sobe se `ERP_SECRET_KEY` for a de exemplo
  ou tiver menos de 32 caracteres. A documentação interativa some em produção.
- **Dados pessoais (LGPD)**: o ERP guarda nome e CPF/RG. Use sempre HTTPS, mantenha o acesso só com quem precisa
  e peça o consentimento de quem viaja. Não há CORS aberto: o painel e a API vivem na mesma origem.

## Estrutura

```
app/
  main.py           aplicação, cabeçalhos de segurança, painel servido por app.frontend()
  config.py db.py   configuração e banco (SQLite local, Postgres em produção)
  models.py         tabelas erp_*
  schemas.py        contratos de entrada e saída
  security.py       login, sessão, CSRF, limitador
  api_publica.py    único ponto que conversa com a API do site (tratamento de queda e recusa)
  eventos_publicos.py   leitura (com cache) dos eventos
  services/         regras de negócio (lotação, espera, pagamentos, documentos)
  routers/          rotas: auth, painel, eventos, linktree, veiculos, reservas, passageiros, contatos
  cli.py            criar-usuario, dados-demo
frontend/           painel (HTML + CSS + JS, sem build), mesma identidade visual do site
tests/              99 testes
```

Seguimos a skill de FastAPI do projeto: `Annotated` nas dependências, dependências de login no `APIRouter`,
tipos de retorno nas rotas, rotas síncronas (`def`) por usar banco síncrono, uma operação HTTP por função e `app.frontend()`
para servir o painel.

## O que ainda não foi testado nem feito

- **Postgres e Vercel.** Os testes rodam em SQLite. O código usa só recursos comuns (e `SELECT ... FOR UPDATE` para
  evitar que duas pessoas peguem o mesmo assento), mas falta rodar contra o Neon. Os arquivos `vercel.json` e
  `api/index.py` seguem o formato da API pública, mas **não foram publicados**.
- **Migrações.** As tabelas são criadas ao iniciar (`create_all`). Para mudar colunas depois, use Alembic.
- **Redefinir senha, vários níveis de acesso** (por enquanto todo usuário pode tudo) e **trilha de auditoria**
  além de “quem registrou cada pagamento”.
- **Lista de embarque para imprimir/exportar** (CSV ou PDF) por van.
- **Criar a van automaticamente** quando um evento novo abre no site, se você quiser esse atalho.
- **A API pública ainda não tem login.** Hoje qualquer pessoa que conheça o endereço consegue criar, editar ou apagar
  eventos. Isso não foi alterado a pedido, mas vale proteger as rotas de escrita em outro momento.
