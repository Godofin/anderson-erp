/* Van fechada: a lista de confirmados vira lista de presença, com um check por ponto da viagem
   (entrada na van, paradas, volta). Usada pela página da van quando ela está fechada. */

import { api, ApiError } from '../api.js';
import { TIPOS_VEICULO, confirmar, etiquetaPagamento, html, idPassageiro, janela, plural, toast } from '../ui.js';

// Lembra o ponto escolhido (e o filtro) enquanto a pessoa mexe, mesmo recarregando a página
const memoria = new Map();

const quando = (iso) => new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' });

const documentoTexto = (p) => `${p.documento_tipo.toUpperCase()} ${p.documento_mascarado}`;

function bolinhas(lista, p) {
    return html`<span class="bolinhas" aria-hidden="true">${lista.pontos.map((pt) =>
        html`<i class="${p.presente_em.includes(pt.id) ? 'ligada' : ''}" title="${pt.nome}"></i>`)}</span>`;
}

function linhaDaLista(lista, ponto, p) {
    const marcado = p.presente_em.includes(ponto.id);
    return html`<li class="presenca-linha ${marcado ? 'marcado' : ''}">
        <button type="button" class="presenca" data-acao="marcar" data-reserva="${p.id}" data-ponto="${ponto.id}"
            aria-pressed="${marcado}" aria-label="${p.passageiro.nome}, assento ${p.assento ?? 'sem assento'}, ${ponto.nome}">
            <i class="ph ${marcado ? 'ph-fill ph-check-square' : 'ph-square'}" aria-hidden="true"></i>
            <span class="assento-mini">${p.assento ?? '-'}</span>
            <span class="quem-linha"><strong>${p.passageiro.nome}</strong>
                <span class="sub">${idPassageiro(p.passageiro.id)} · ${documentoTexto(p.passageiro)}</span></span>
            ${bolinhas(lista, p)}
        </button>
        <div class="pagto-linha">${etiquetaPagamento(p.status_pagamento)}
            <button type="button" class="btn btn-neutro btn-pequeno" data-acao="pagamento" data-reserva="${p.id}">
                <i class="ph ph-currency-circle-dollar" aria-hidden="true"></i>Pagamento</button></div>
    </li>`;
}

/** Tudo que muda quando alguém é marcado: abas com contagem e a lista do ponto escolhido. */
function corpoDaLista(lista, estado) {
    const ponto = lista.pontos.find((p) => p.id === estado.ponto) || lista.pontos[0];
    estado.ponto = ponto?.id;
    const visiveis = lista.passageiros.filter((p) => !estado.soFaltam || !p.presente_em.includes(ponto.id));
    return html`
        <div class="segmentos pontos-abas" role="group" aria-label="Pontos da viagem">
            ${lista.pontos.map((pt) => html`<button type="button" data-acao="ponto" data-ponto="${pt.id}" aria-pressed="${pt.id === ponto.id}">
                ${pt.nome}<span class="contagem">${pt.presentes}/${pt.total}</span></button>`)}
        </div>
        <div class="barra-ponto">
            <div><h3>${ponto.nome}</h3>
                <p class="muted" aria-live="polite">${ponto.presentes === ponto.total
                    ? `Todos conferidos (${ponto.total}).`
                    : `${plural(ponto.presentes, 'passageiro conferido', 'passageiros conferidos')} de ${ponto.total}. Faltam ${ponto.total - ponto.presentes}.`}</p></div>
            <div class="acoes-linha">
                <label class="check"><input type="checkbox" data-acao="so-faltam" ${estado.soFaltam ? 'checked' : ''}><span>Só quem falta</span></label>
                <button type="button" class="btn btn-ok btn-pequeno" data-acao="todos" data-ponto="${ponto.id}" data-valor="true"
                    ${ponto.presentes === ponto.total ? 'disabled' : ''}><i class="ph ph-checks" aria-hidden="true"></i>Marcar todos</button>
                <button type="button" class="btn btn-neutro btn-pequeno" data-acao="todos" data-ponto="${ponto.id}" data-valor="false"
                    ${ponto.presentes === 0 ? 'disabled' : ''}>Limpar</button>
            </div>
        </div>
        ${visiveis.length
            ? html`<ul class="lista-presenca">${visiveis.map((p) => linhaDaLista(lista, ponto, p))}</ul>`
            : html`<div class="painel vazio"><i class="ph ph-check-circle" aria-hidden="true"></i><h3>Todo mundo conferido</h3>
                <p>Ninguém falta marcar em "${ponto.nome}".</p></div>`}`;
}

export async function renderizarFechada(raiz, ctx, v, evento) {
    const lista = await api.get(`/api/veiculos/${v.id}/lista`);
    const estado = memoria.get(v.id) || { ponto: null, soFaltam: false };
    memoria.set(v.id, estado);
    raiz._lista = lista;
    raiz._estado = estado;
    raiz._fechada = true;
    raiz._dados = { v, evento };
    raiz._mapa = new Map(lista.passageiros.map((r) => [String(r.id), r]));
    raiz.innerHTML = html`
        <a class="voltar" href="#/eventos/${evento.id}"><i class="ph ph-arrow-left" aria-hidden="true"></i>${evento.titulo}</a>
        <div class="cabecalho">
            <div class="titulo">
                <h1>${v.nome}</h1>
                <p>${TIPOS_VEICULO[v.tipo]}${v.placa ? ` · placa ${v.placa}` : ''} · ${evento.data_texto}</p>
                <div class="chips"><span class="etiqueta ok"><i class="ph-fill ph-lock-simple" aria-hidden="true"></i>Van fechada</span>
                    <span class="muted">em ${quando(lista.fechada_em)} por ${lista.fechada_por}</span></div>
            </div>
            <div class="acoes">
                <button class="btn btn-neutro" type="button" data-acao="pontos"><i class="ph ph-list-checks" aria-hidden="true"></i>Editar pontos</button>
                <button class="btn btn-neutro" type="button" data-acao="reabrir"><i class="ph ph-lock-simple-open" aria-hidden="true"></i>Reabrir van</button>
            </div>
        </div>
        ${lista.fora_da_lista
            ? html`<div class="alerta" role="status"><i class="ph ph-info" aria-hidden="true"></i>
                <div>${plural(lista.fora_da_lista, 'pessoa ficou', 'pessoas ficaram')} na lista de espera e não entra${lista.fora_da_lista === 1 ? '' : 'm'} nesta lista de presença.</div></div>`
            : ''}
        <section class="secao" aria-labelledby="t-lista">
            <div class="secao-topo"><h2 id="t-lista">Lista de presença (${lista.passageiros.length})</h2>
                <span class="muted">Toque no nome para marcar quem está na van neste ponto.</span></div>
            <div class="painel"><div class="painel-corpo" id="corpo-lista">${corpoDaLista(lista, estado)}</div></div>
        </section>`.toString();
}

export function ligarFechada(raiz, ctx, abrirPagamento) {
    const { v } = raiz._dados;
    const estado = raiz._estado;
    const corpo = raiz.querySelector('#corpo-lista');
    const falhar = (erro) => toast(erro instanceof ApiError ? erro.message : 'Algo deu errado.', 'erro');

    const aplicar = (lista) => {
        raiz._lista = lista;
        raiz._mapa = new Map(lista.passageiros.map((r) => [String(r.id), r]));
        corpo.innerHTML = corpoDaLista(lista, estado).toString();
        raiz.querySelector('#t-lista').textContent = `Lista de presença (${lista.passageiros.length})`;
    };

    raiz.addEventListener('change', (ev) => {
        if (ev.target.matches('[data-acao="so-faltam"]')) {
            estado.soFaltam = ev.target.checked;
            aplicar(raiz._lista);
        }
    });

    raiz.addEventListener('click', async (ev) => {
        const alvo = ev.target.closest('[data-acao]');
        if (!alvo || alvo.matches('input')) return;
        try {
            switch (alvo.dataset.acao) {
                case 'ponto':
                    estado.ponto = Number(alvo.dataset.ponto);
                    return aplicar(raiz._lista);
                case 'marcar': {
                    const pontoId = Number(alvo.dataset.ponto);
                    const pessoa = raiz._mapa.get(alvo.dataset.reserva);
                    const marcar = !pessoa.presente_em.includes(pontoId);
                    // Responde na hora e confirma com o servidor em seguida
                    const antes = raiz._lista;
                    pessoa.presente_em = marcar ? [...pessoa.presente_em, pontoId] : pessoa.presente_em.filter((x) => x !== pontoId);
                    const ponto = antes.pontos.find((p) => p.id === pontoId);
                    ponto.presentes += marcar ? 1 : -1;
                    aplicar(antes);
                    try {
                        aplicar(await api.put(`/api/pontos/${pontoId}/presencas/${pessoa.id}`, { presente: marcar }));
                    } catch (erro) {
                        ctx.recarregar();
                        throw erro;
                    }
                    return;
                }
                case 'todos': {
                    const marcar = alvo.dataset.valor === 'true';
                    return aplicar(await api.post(`/api/pontos/${alvo.dataset.ponto}/presencas`, { presente: marcar }));
                }
                case 'pagamento':
                    return abrirPagamento(raiz._mapa.get(alvo.dataset.reserva), (m) => { if (m) toast(m); ctx.recarregar(); });
                case 'pontos':
                    return dialogPontos(raiz._lista, ctx);
                case 'reabrir': {
                    const feitos = raiz._lista.pontos.reduce((soma, p) => soma + p.presentes, 0);
                    const sim = await confirmar({
                        titulo: 'Reabrir esta van?',
                        mensagem: `A lista volta a aceitar mudanças (entrar, sair, trocar de assento).${feitos ? ` As ${feitos} marcações já feitas ficam guardadas.` : ''}`,
                        rotulo: 'Reabrir van',
                    });
                    if (!sim) return;
                    await api.post(`/api/veiculos/${v.id}/reabrir`);
                    toast('Van reaberta');
                    return ctx.recarregar();
                }
                default:
            }
        } catch (erro) {
            falhar(erro);
        }
    });
}

function dialogPontos(lista, ctx) {
    janela({
        titulo: 'Pontos da viagem',
        botao: 'Salvar',
        conteudo: html`
            <p class="muted">Em cada ponto você confere quem está na van. Renomeie, apague ou acrescente (até 12).</p>
            ${lista.pontos.map((p) => html`<div class="linha-ponto">
                <div class="campo"><label class="sr-only" for="ponto-${p.id}">Nome do ponto</label>
                    <input type="text" id="ponto-${p.id}" name="ponto-${p.id}" value="${p.nome}" maxlength="60" required></div>
                <button type="button" class="btn btn-perigo btn-pequeno" data-apagar-ponto="${p.id}" data-nome="${p.nome}">
                    <i class="ph ph-trash" aria-hidden="true"></i>Apagar</button></div>`)}
            <div class="campo"><label for="ponto-novo">Novo ponto (opcional)</label>
                <input type="text" id="ponto-novo" name="novo" maxlength="60" placeholder="Parada do almoço" autocomplete="off"></div>`,
        aoAbrir: (d) => {
            d.querySelectorAll('[data-apagar-ponto]').forEach((b) => b.addEventListener('click', async () => {
                const sim = await confirmar({
                    titulo: `Apagar "${b.dataset.nome}"?`,
                    mensagem: 'As marcações feitas nesse ponto também são apagadas.',
                    rotulo: 'Apagar ponto',
                    perigo: true,
                });
                if (!sim) return;
                try {
                    await api.del(`/api/pontos/${b.dataset.apagarPonto}`);
                    d.close();
                    toast('Ponto apagado');
                    ctx.recarregar();
                } catch (erro) {
                    d.mostrarErro(erro.message);
                }
            }));
        },
        aoEnviar: async (dados) => {
            for (const p of lista.pontos) {
                const nome = String(dados.get(`ponto-${p.id}`) || '').trim();
                if (nome && nome !== p.nome) await api.patch(`/api/pontos/${p.id}`, { nome });
            }
            const novo = String(dados.get('novo') || '').trim();
            if (novo) await api.post(`/api/veiculos/${lista.veiculo.id}/pontos`, { nome: novo });
            toast('Pontos atualizados');
            ctx.recarregar();
        },
    });
}
