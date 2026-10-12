/* Estrutura do ERP: login, menu, rotas por hash (#/painel, #/eventos/12...) e tratamento de sessão. */

import { api, ApiError } from './api.js';
import { aplicarMedidas, esqueleto, html } from './ui.js';

const app = document.getElementById('app');
let usuario = null;

const ROTAS = [
    { re: /^#\/painel$/, modulo: './paginas/painel.js', menu: 'painel', titulo: 'Painel' },
    { re: /^#\/eventos$/, modulo: './paginas/eventos.js', menu: 'eventos', titulo: 'Eventos e vans' },
    { re: /^#\/eventos\/novo$/, modulo: './paginas/evento_form.js', menu: 'eventos', titulo: 'Novo evento' },
    { re: /^#\/eventos\/(\d+)\/editar$/, modulo: './paginas/evento_form.js', menu: 'eventos', titulo: 'Editar evento' },
    { re: /^#\/eventos\/(\d+)$/, modulo: './paginas/evento.js', menu: 'eventos', titulo: 'Viagem' },
    { re: /^#\/veiculos\/(\d+)$/, modulo: './paginas/veiculo.js', menu: 'eventos', titulo: 'Van' },
    { re: /^#\/passageiros$/, modulo: './paginas/passageiros.js', menu: 'passageiros', titulo: 'Passageiros' },
    { re: /^#\/contatos$/, modulo: './paginas/contatos.js', menu: 'contatos', titulo: 'Contatos' },
    { re: /^#\/linktree$/, modulo: './paginas/linktree.js', menu: 'linktree', titulo: 'Linktree' },
];

const MENU = [
    ['painel', '#/painel', 'ph-squares-four', 'Painel'],
    ['eventos', '#/eventos', 'ph-bus', 'Eventos e vans'],
    ['passageiros', '#/passageiros', 'ph-users-three', 'Passageiros'],
    ['contatos', '#/contatos', 'ph-address-book', 'Contatos'],
    ['linktree', '#/linktree', 'ph-link', 'Linktree do site'],
];

const logo = html`<a class="logo" href="#/painel" aria-label="Anderson Viagem e Turismo, painel" translate="no">
    <img class="logo-escuro" src="assets/logo-escuro.png" alt="" width="132" height="64">
    <img class="logo-claro" src="assets/logo-claro.png" alt="" width="132" height="64"></a>`;

// ------------------------------------------------------------------ tema
function alternarTema() {
    const atual = document.documentElement.dataset.theme
        || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
    const novo = atual === 'light' ? 'dark' : 'light';
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem('erp-tema', novo); } catch (e) { /* sem armazenamento: o tema só vale nesta sessão */ }
}

// ------------------------------------------------------------------ login
function mostrarLogin(aviso = '') {
    usuario = null;
    document.title = 'Entrar | ERP Anderson';
    app.innerHTML = html`<main class="entrada" id="conteudo">
        <div class="entrada-cartao">
            ${logo}
            <div><h1>ERP</h1><p>Vans, passageiros e pagamentos. Acesso só para a equipe.</p></div>
            ${aviso ? html`<div class="alerta" role="status"><i class="ph ph-info" aria-hidden="true"></i><div>${aviso}</div></div>` : ''}
            <form id="form-login" novalidate>
                <div class="campo"><label for="email">E-mail</label>
                    <input type="email" id="email" name="email" autocomplete="username" autocapitalize="none" spellcheck="false" required></div>
                <div class="campo"><label for="senha">Senha</label>
                    <input type="password" id="senha" name="senha" autocomplete="current-password" required></div>
                <p class="erro" id="erro-login" role="alert" hidden></p>
                <button class="btn btn-primario btn-bloco" type="submit">Entrar</button>
            </form>
            <p class="muted">Esqueceu a senha? Peça para quem administra o ERP trocar.</p>
        </div></main>`.toString();
    const form = document.getElementById('form-login');
    const erro = document.getElementById('erro-login');
    document.getElementById('email').focus();
    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const dados = new FormData(form);
        const botao = form.querySelector('button');
        erro.hidden = true;
        botao.disabled = true;
        try {
            usuario = await api.post('/api/auth/login', { email: dados.get('email').trim(), senha: dados.get('senha') });
            iniciarEstrutura();
        } catch (e) {
            erro.textContent = e instanceof ApiError ? e.message : 'Não foi possível entrar.';
            erro.hidden = false;
            botao.disabled = false;
        }
    });
}

// ------------------------------------------------------------------ estrutura
function iniciarEstrutura() {
    app.innerHTML = html`<div class="shell">
        <header class="topo-celular">
            ${logo}
            <button class="btn btn-neutro btn-icone" id="abrir-menu" type="button" aria-label="Abrir menu" aria-expanded="false" aria-controls="menu-lateral">
                <i class="ph ph-list" aria-hidden="true"></i></button>
        </header>
        <aside class="lateral" id="menu-lateral">
            ${logo}
            <nav aria-label="Principal"><ul class="menu">
                ${MENU.map(([chave, href, icone, texto]) => html`<li><a href="${href}" data-menu="${chave}"><i class="ph ${icone}" aria-hidden="true"></i>${texto}</a></li>`)}
            </ul></nav>
            <div class="lateral-rodape">
                <div class="usuario"><strong>${usuario.nome}</strong><span>${usuario.email}</span></div>
                <div class="linha-botoes">
                    <button class="btn btn-neutro btn-pequeno" id="tema" type="button"><i class="ph ph-circle-half" aria-hidden="true"></i>Tema</button>
                    <button class="btn btn-neutro btn-pequeno" id="sair" type="button"><i class="ph ph-sign-out" aria-hidden="true"></i>Sair</button>
                </div>
            </div>
        </aside>
        <main class="conteudo" id="conteudo" tabindex="-1"></main>
    </div>`.toString();

    const menu = document.getElementById('menu-lateral');
    const abrir = document.getElementById('abrir-menu');
    const fechar = () => { menu.classList.remove('aberta'); abrir.setAttribute('aria-expanded', 'false'); };
    abrir.addEventListener('click', () => {
        const aberta = menu.classList.toggle('aberta');
        abrir.setAttribute('aria-expanded', String(aberta));
    });
    menu.addEventListener('click', (ev) => { if (ev.target.closest('a')) fechar(); });
    document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') fechar(); });
    document.getElementById('tema').addEventListener('click', alternarTema);
    document.getElementById('sair').addEventListener('click', async () => {
        try { await api.post('/api/auth/logout'); } catch (e) { /* já saiu */ }
        location.hash = '';
        mostrarLogin();
    });
    if (!location.hash || location.hash === '#/' || location.hash === '#') location.replace('#/painel');
    else rotear();
}

// ------------------------------------------------------------------ rotas
let numeroDaNavegacao = 0;

function novoPrincipal() {
    const el = document.createElement('main');
    el.className = 'conteudo';
    el.id = 'conteudo';
    el.tabIndex = -1;
    return el;
}

/**
 * Abre a página do endereço atual. Com manterPosicao (usado depois de salvar algo), mantém o conteúdo
 * antigo na tela até o novo ficar pronto e devolve a rolagem para onde estava.
 */
async function rotear(manterPosicao = false) {
    if (!usuario) return;
    const principal = document.getElementById('conteudo');
    if (!principal) return;
    const hash = location.hash || '#/painel';
    const rota = ROTAS.map((r) => ({ r, m: hash.match(r.re) })).find((x) => x.m);
    document.querySelectorAll('[data-menu]').forEach((a) => {
        if (rota && a.dataset.menu === rota.r.menu) a.setAttribute('aria-current', 'page');
        else a.removeAttribute('aria-current');
    });
    if (!rota) {
        principal.innerHTML = html`<div class="painel vazio"><i class="ph ph-compass" aria-hidden="true"></i>
            <h3>Página não encontrada</h3><p>Esse endereço não existe no ERP.</p>
            <a class="btn btn-primario" href="#/painel">Ir para o painel</a></div>`.toString();
        return;
    }
    const minha = ++numeroDaNavegacao;
    const rolagem = window.scrollY;
    document.title = `${rota.r.titulo} | ERP Anderson`;
    if (!manterPosicao) principal.innerHTML = esqueleto(5).toString();
    try {
        const modulo = await import(rota.r.modulo);
        const contexto = {
            usuario,
            ids: rota.m.slice(1).map(Number),
            recarregar: () => rotear(true),
            titulo: (texto) => { document.title = `${texto} | ERP Anderson`; },
        };
        const novo = novoPrincipal();
        await modulo.renderizar(novo, contexto);
        if (minha !== numeroDaNavegacao) return; // o usuário já foi para outra página
        principal.replaceWith(novo);
        aplicarMedidas(novo);
        modulo.ligar?.(novo, contexto);
        window.scrollTo({ top: manterPosicao ? rolagem : 0 });
    } catch (erro) {
        if (minha !== numeroDaNavegacao) return;
        if (erro instanceof ApiError && erro.status === 401) return; // a sessão expirou: o login já aparece
        principal.innerHTML = html`<div class="alerta erro" role="alert"><i class="ph ph-warning-circle" aria-hidden="true"></i>
            <div><strong>Não consegui abrir esta página.</strong><span>${erro instanceof ApiError ? erro.message : 'Erro inesperado.'}</span>
            <div><button class="btn btn-neutro btn-pequeno" id="tentar-de-novo" type="button">Tentar de novo</button></div></div></div>`.toString();
        document.getElementById('tentar-de-novo')?.addEventListener('click', () => rotear());
        if (!(erro instanceof ApiError)) console.error(erro);
    }
}

window.addEventListener('hashchange', () => rotear());
window.addEventListener('sessao-expirada', () => mostrarLogin('Sua sessão expirou. Entre de novo para continuar.'));

// ------------------------------------------------------------------ início
(async function iniciar() {
    try {
        usuario = await api.get('/api/auth/eu');
        iniciarEstrutura();
    } catch (erro) {
        if (erro instanceof ApiError && erro.status === 401) mostrarLogin();
        else {
            app.innerHTML = html`<main class="entrada" id="conteudo"><div class="entrada-cartao">
                <h1>Sem conexão</h1><p>${erro.message}</p>
                <button class="btn btn-primario" type="button" id="recarregar">Tentar de novo</button></div></main>`.toString();
            document.getElementById('recarregar').addEventListener('click', () => location.reload());
        }
    }
})();

