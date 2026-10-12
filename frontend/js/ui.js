/* Peças de interface: HTML seguro, formatadores, etiquetas, janelas e avisos. */

import { ApiError } from './api.js';

// ------------------------------------------------------------------ HTML seguro
const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (valor) => String(valor ?? '').replace(/[&<>"']/g, (c) => ESCAPES[c]);

class Seguro {
    constructor(texto) { this.texto = texto; }
    toString() { return this.texto; }
}
const converter = (v) => {
    if (v instanceof Seguro) return v.texto;
    if (Array.isArray(v)) return v.map(converter).join('');
    if (v === null || v === undefined || v === false) return '';
    return esc(v);
};
/** Modelo de HTML: tudo que entra por ${...} é escapado, exceto o que vier de outro html`...`. */
export function html(partes, ...valores) {
    let saida = partes[0];
    valores.forEach((v, i) => { saida += converter(v) + partes[i + 1]; });
    return new Seguro(saida);
}

/** Aplica larguras de barras (via CSSOM, que a política de segurança permite). */
export function aplicarMedidas(raiz) {
    raiz.querySelectorAll('[data-pct]').forEach((el) => el.style.setProperty('--pct', `${el.dataset.pct}%`));
}

// ------------------------------------------------------------------ formatadores
const moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
export const brl = (centavos) => moeda.format((centavos || 0) / 100);

/** "1.234,56" -> 123456 (centavos). Devolve NaN se não for um valor. */
export function lerReais(texto) {
    let t = String(texto ?? '').trim().replace(/[^\d,.]/g, '');
    if (!t) return NaN;
    if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
    else if (!/^\d+\.\d{1,2}$/.test(t)) t = t.replace(/\./g, '');
    const numero = Number.parseFloat(t);
    return Number.isFinite(numero) ? Math.round(numero * 100) : NaN;
}
export const reaisParaCampo = (centavos) => (centavos / 100).toFixed(2).replace('.', ',');

export function dataBr(iso) {
    if (!iso) return '';
    const [a, m, d] = iso.slice(0, 10).split('-');
    return `${d}/${m}/${a}`;
}
export const hojeISO = () => {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};
export function diasAte(iso) {
    if (!iso) return null;
    const [a, m, d] = iso.slice(0, 10).split('-').map(Number);
    const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
    return Math.round((new Date(a, m - 1, d) - hoje) / 86400000);
}
export const quandoFalta = (iso) => {
    const n = diasAte(iso);
    if (n === null) return '';
    if (n < 0) return 'Já passou';
    if (n === 0) return 'É hoje';
    if (n === 1) return 'Amanhã';
    return `Em ${n} dias`;
};

export const idPassageiro = (id) => `P-${String(id).padStart(5, '0')}`;
export const primeiroNome = (nome) => String(nome || '').trim().split(/\s+/)[0] || '';
export const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

export function linkWhatsApp(telefone) {
    const d = String(telefone || '').replace(/\D/g, '');
    if (d.length < 10) return '';
    return `https://wa.me/${d.startsWith('55') && d.length >= 12 ? d : '55' + d}`;
}

export const TIPOS_VEICULO = { van: 'Van', micro_onibus: 'Micro-ônibus', onibus: 'Ônibus' };
export const ICONE_VEICULO = { van: 'ph-van', micro_onibus: 'ph-bus', onibus: 'ph-bus' };
export const CATEGORIAS = {
    motorista: 'Motorista',
    empresa_fretamento: 'Empresa de fretamento',
    guia: 'Guia',
    fornecedor: 'Fornecedor',
    outro: 'Outro',
};

// ------------------------------------------------------------------ etiquetas de estado (sempre ícone + texto)
export function etiquetaPagamento(status) {
    const mapa = {
        pago: ['ok', 'ph-fill ph-check-circle', 'Pago'],
        parcial: ['atencao', 'ph-fill ph-circle-half', 'Parcial'],
        pendente: ['erro', 'ph-fill ph-warning-circle', 'Pendente'],
        sem_valor: ['neutra', 'ph ph-minus-circle', 'Sem valor'],
    };
    const [tom, icone, texto] = mapa[status] || mapa.pendente;
    return html`<span class="etiqueta ${tom}"><i class="${icone}" aria-hidden="true"></i>${texto}</span>`;
}

export function barraOcupacao(confirmados, capacidade) {
    const pct = capacidade ? Math.min(100, Math.round((confirmados / capacidade) * 100)) : 0;
    const cheia = capacidade > 0 && confirmados >= capacidade;
    return html`<div class="ocupacao">
        <div class="linha"><span>Assentos</span><strong>${confirmados}/${capacidade}</strong></div>
        <div class="barra ${cheia ? 'cheia' : ''}" role="img" aria-label="${confirmados} de ${capacidade} assentos ocupados"><span data-pct="${pct}"></span></div>
    </div>`;
}

/** Só a barra, sem o rótulo (para usar dentro dos cartões de números). */
export function barraSimples(confirmados, capacidade) {
    const pct = capacidade ? Math.min(100, Math.round((confirmados / capacidade) * 100)) : 0;
    const cheia = capacidade > 0 && confirmados >= capacidade;
    return html`<div class="barra ${cheia ? 'cheia' : ''}" role="img" aria-label="${confirmados} de ${capacidade} assentos ocupados"><span data-pct="${pct}"></span></div>`;
}

// ------------------------------------------------------------------ avisos
export function toast(mensagem, tipo = 'ok') {
    const area = document.getElementById('toasts');
    if (!area) return;
    const el = document.createElement('div');
    el.className = `toast${tipo === 'erro' ? ' erro' : ''}`;
    el.textContent = mensagem;
    area.append(el);
    setTimeout(() => el.remove(), tipo === 'erro' ? 6000 : 3200);
}

export function debounce(fn, ms = 250) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

/** Escuta eventos de uma região e resolve o elemento com data-acao mais próximo (sem handlers inline). */
export function ouvirAcoes(raiz, tipo, funcao) {
    raiz.addEventListener(tipo, (ev) => {
        const alvo = ev.target.closest('[data-acao]');
        if (alvo && raiz.contains(alvo)) funcao(alvo.dataset.acao, alvo, ev);
    });
}

// ------------------------------------------------------------------ janelas (dialog nativo)
/**
 * Abre uma janela de formulário. aoEnviar recebe os campos; se lançar ApiError, o erro aparece na janela.
 * Retorna o <dialog> para quem quiser ligar eventos extras.
 */
export function janela({ titulo, conteudo, botao = 'Salvar', perigo = false, aoEnviar, aoAbrir, largura }) {
    const dlg = document.createElement('dialog');
    dlg.className = 'janela';
    if (largura) dlg.style.setProperty('width', largura);
    const id = `j${Math.random().toString(36).slice(2, 8)}`;
    dlg.setAttribute('aria-labelledby', `${id}-t`);
    dlg.innerHTML = html`<form method="dialog" novalidate>
        <div class="janela-topo">
            <h2 id="${id}-t">${titulo}</h2>
            <button type="button" class="btn btn-neutro btn-pequeno btn-icone" data-fechar aria-label="Fechar"><i class="ph ph-x" aria-hidden="true"></i></button>
        </div>
        <div class="janela-corpo">
            ${conteudo}
            <p class="campo"><span class="erro" data-erro-geral role="alert" hidden></span></p>
        </div>
        <div class="janela-pe">
            <button type="button" class="btn btn-neutro" data-fechar>Cancelar</button>
            ${botao ? html`<button type="submit" class="btn ${perigo ? 'btn-perigo' : 'btn-primario'}" data-enviar>${botao}</button>` : ''}
        </div>
    </form>`.toString();
    document.body.append(dlg);
    const form = dlg.querySelector('form');
    const mostrarErro = (msg) => {
        const el = dlg.querySelector('[data-erro-geral]');
        el.textContent = msg || '';
        el.hidden = !msg;
    };
    dlg.mostrarErro = mostrarErro;
    dlg.querySelectorAll('[data-fechar]').forEach((b) => b.addEventListener('click', () => dlg.close()));
    dlg.addEventListener('close', () => dlg.remove());
    dlg.addEventListener('click', (ev) => { if (ev.target === dlg) dlg.close(); });
    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        if (!aoEnviar) return;
        const enviar = dlg.querySelector('[data-enviar]');
        mostrarErro('');
        enviar.disabled = true;
        try {
            const resultado = await aoEnviar(new FormData(form), dlg);
            if (resultado !== false) dlg.close();
        } catch (erro) {
            mostrarErro(erro instanceof ApiError ? erro.message : 'Algo deu errado. Tente de novo.');
            if (!(erro instanceof ApiError)) console.error(erro);
        } finally {
            enviar.disabled = false;
        }
    });
    dlg.showModal();
    if (aoAbrir) aoAbrir(dlg);
    const primeiro = dlg.querySelector('input:not([type=hidden]):not([disabled]), select, textarea');
    if (primeiro) primeiro.focus();
    return dlg;
}

/** Pergunta de confirmação. Resolve true/false. */
export function confirmar({ titulo, mensagem, rotulo = 'Confirmar', perigo = false }) {
    return new Promise((resolve) => {
        let resposta = false;
        const dlg = janela({
            titulo,
            conteudo: html`<p>${mensagem}</p>`,
            botao: rotulo,
            perigo,
            aoEnviar: () => { resposta = true; },
        });
        dlg.addEventListener('close', () => resolve(resposta));
    });
}

/** Erro de validação feito na própria tela: aparece na janela como qualquer outro erro. */
export const erroDeTela = (mensagem) => new ApiError(422, mensagem);

export const campoErro = (el, msg) => {
    const alvo = el.closest('.campo')?.querySelector('.erro');
    el.setAttribute('aria-invalid', msg ? 'true' : 'false');
    if (alvo) { alvo.textContent = msg || ''; alvo.hidden = !msg; }
};

export const estadoVazio = (icone, titulo, texto, acao = '') => html`<div class="painel vazio">
    <i class="ph ${icone}" aria-hidden="true"></i><h3>${titulo}</h3><p>${texto}</p>${acao}</div>`;

export const esqueleto = (linhas = 4) =>
    html`<div class="esqueleto" aria-hidden="true">${Array.from({ length: linhas }, () => html`<span></span>`)}</div>`;
