import { api } from '../api.js';
import { linhaEvento } from '../componentes.js';
import { brl, estadoVazio, etiquetaPagamento, html, plural, quandoFalta } from '../ui.js';

const hora = (iso) => {
    const d = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    return d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
};

export async function renderizar(raiz) {
    const p = await api.get('/api/painel');
    const ocupacao = p.assentos ? Math.round((p.confirmados / p.assentos) * 100) : 0;

    raiz.innerHTML = html`
        <div class="cabecalho">
            <div class="titulo"><h1>Painel</h1><p>Atualizado às ${hora(p.gerado_em)}. Mostra só as viagens que ainda vão acontecer.</p></div>
            <div class="acoes"><button class="btn btn-neutro" type="button" data-acao="atualizar"><i class="ph ph-arrows-clockwise" aria-hidden="true"></i>Atualizar</button></div>
        </div>

        <div class="numeros" role="list">
            <div class="numero" role="listitem"><span class="rotulo-num">Próximas viagens</span><strong>${p.proximas_viagens}</strong><small>abertas no site</small></div>
            <div class="numero" role="listitem"><span class="rotulo-num">Assentos ocupados</span><strong>${p.confirmados}<small> de ${p.assentos}</small></strong><small>${p.assentos ? `${ocupacao}% das vans cadastradas` : 'nenhuma van cadastrada ainda'}</small></div>
            <div class="numero" role="listitem"><span class="rotulo-num">Lista de espera</span><strong>${p.em_espera}</strong><small>${p.em_espera ? 'pessoas aguardando vaga' : 'ninguém esperando'}</small></div>
            <div class="numero destaque" role="listitem"><span class="rotulo-num">A receber</span><strong>${brl(p.a_receber_centavos)}</strong><small>já recebido: ${brl(p.pago_centavos)}</small></div>
        </div>

        ${p.sem_veiculo.length ? html`
        <section class="secao" aria-labelledby="t-sem-van">
            <div class="alerta"><i class="ph-fill ph-warning" aria-hidden="true"></i><div>
                <strong id="t-sem-van">${plural(p.sem_veiculo.length, 'viagem chega', 'viagens chegam')} sem van cadastrada</strong>
                <ul>${p.sem_veiculo.map((e) => html`<li><a href="#/eventos/${e.id}">${e.titulo}</a> <span class="muted">· ${quandoFalta(e.data_inicio)}</span></li>`)}</ul>
            </div></div>
        </section>` : ''}

        <section class="secao" aria-labelledby="t-pendencias">
            <div class="secao-topo"><h2 id="t-pendencias">Pagamentos a receber</h2></div>
            ${p.pendencias.length ? html`<div class="tabela-rolagem"><table>
                <caption class="sr-only">Passageiros confirmados com saldo em aberto</caption>
                <thead><tr><th>Passageiro</th><th>Viagem</th><th>Pagamento</th><th class="direita">Falta pagar</th><th><span class="sr-only">Abrir</span></th></tr></thead>
                <tbody>${p.pendencias.map((x) => html`<tr>
                    <td><span class="nome">${x.passageiro}</span></td>
                    <td>${x.evento_titulo || 'Viagem'}</td>
                    <td>${etiquetaPagamento(x.status_pagamento)}</td>
                    <td class="direita num">${brl(x.saldo_centavos)}</td>
                    <td class="direita"><a class="btn btn-neutro btn-pequeno" href="#/veiculos/${x.veiculo_id}">Abrir van</a></td></tr>`)}</tbody>
            </table></div>` : estadoVazio('ph-check-circle', 'Nada a receber agora', 'Todos os passageiros confirmados estão com o pagamento em dia, ou ainda não há passageiros cadastrados.')}
        </section>

        <section class="secao" aria-labelledby="t-proximas">
            <div class="secao-topo"><h2 id="t-proximas">Próximas viagens</h2><a class="btn btn-neutro btn-pequeno" href="#/eventos">Ver todas</a></div>
            ${p.proximos.length
                ? html`<div class="lista-eventos">${p.proximos.map(linhaEvento)}</div>`
                : estadoVazio('ph-calendar-blank', 'Nenhuma viagem aberta', 'Quando um evento for cadastrado no site, ele aparece aqui sozinho.')}
        </section>`.toString();
}

export function ligar(raiz, ctx) {
    raiz.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-acao="atualizar"]')) ctx.recarregar();
    });
}
