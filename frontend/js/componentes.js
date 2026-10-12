/* Blocos de tela usados em mais de uma página. */

import { ICONE_VEICULO, TIPOS_VEICULO, barraOcupacao, brl, html, plural, quandoFalta } from './ui.js';

export function linhaEvento(e) {
    const quando = e.data_inicio ? quandoFalta(e.data_inicio) : '';
    return html`<a class="evento-linha" href="#/eventos/${e.id}">
        <div class="miniatura">${e.imagem
            ? html`<img src="${e.imagem}" alt="" width="72" height="72" loading="lazy" referrerpolicy="no-referrer">`
            : html`<i class="ph ph-image" aria-hidden="true"></i>`}</div>
        <div class="info">
            <strong>${e.titulo}</strong>
            <span>${e.data_texto}</span>
            <span>${quando}${!e.ativo ? ' · Fora do site' : ''}</span>
        </div>
        <div>${e.veiculos
            ? html`${barraOcupacao(e.confirmados, e.assentos)}`
            : html`<span class="etiqueta erro"><i class="ph-fill ph-warning" aria-hidden="true"></i>Sem van cadastrada</span>`}</div>
        <div class="dinheiro">
            <span>Recebido <strong>${brl(e.pago_centavos)}</strong></span>
            <span>A receber <strong>${brl(e.a_receber_centavos)}</strong></span>
        </div>
        <div>${e.em_espera
            ? html`<span class="etiqueta neutra"><i class="ph ph-hourglass-medium" aria-hidden="true"></i>${e.em_espera} na espera</span>`
            : ''}</div>
    </a>`;
}

export function cartaoVan(v) {
    return html`<a class="van-cartao" href="#/veiculos/${v.id}">
        <div class="topo">
            <div><h3>${v.nome}</h3>
                <span class="muted">${TIPOS_VEICULO[v.tipo]}${v.placa ? ` · ${v.placa}` : ''}</span>
                ${v.fechada ? html`<div><span class="etiqueta ok"><i class="ph-fill ph-lock-simple" aria-hidden="true"></i>Fechada</span></div>` : ''}</div>
            <i class="ph ${ICONE_VEICULO[v.tipo]}" aria-hidden="true"></i>
        </div>
        ${barraOcupacao(v.confirmados, v.capacidade)}
        <div class="meta">
            ${v.em_espera
                ? html`<span><i class="ph ph-hourglass-medium" aria-hidden="true"></i>${plural(v.em_espera, 'pessoa', 'pessoas')} na lista de espera</span>`
                : ''}
            ${v.contato
                ? html`<span><i class="ph ph-steering-wheel" aria-hidden="true"></i>${v.contato.nome}${v.contato.telefone ? ` · ${v.contato.telefone}` : ''}</span>`
                : html`<span><i class="ph ph-user-minus" aria-hidden="true"></i>Sem motorista ou empresa ligada</span>`}
        </div>
        <div class="rodape">
            <span>Recebido <strong>${brl(v.pago_centavos)}</strong></span>
            <span>A receber <strong>${brl(v.a_receber_centavos)}</strong></span>
        </div>
    </a>`;
}
