import { api, ApiError } from '../api.js';
import {
    TIPOS_VEICULO, barraSimples, brl, confirmar, dataBr, debounce, erroDeTela,
    estadoVazio, etiquetaPagamento, hojeISO, html, idPassageiro, janela, lerReais, linkWhatsApp, ouvirAcoes,
    plural, primeiroNome, reaisParaCampo, toast,
} from '../ui.js';
import { abrirDetalhe } from './passageiros.js';

const documentoTexto = (p) => `${p.documento_tipo.toUpperCase()} ${p.documento_mascarado}`;

// ------------------------------------------------------------------ renderização
function celulaPassageiro(r) {
    return html`<button type="button" class="link-btn" data-acao="ver-passageiro" data-passageiro="${r.passageiro.id}">
        <span class="nome">${r.passageiro.nome}</span></button>
        <div class="id-pessoa">${idPassageiro(r.passageiro.id)}</div>`;
}

function menuMais(r, itens) {
    return html`<details class="menu-mais"><summary class="btn btn-neutro btn-pequeno btn-icone" aria-label="Mais ações para ${r.passageiro.nome}">
        <i class="ph ph-dots-three-vertical" aria-hidden="true"></i></summary>
        <div class="lista">${itens.map((i) => (i === '---'
            ? html`<hr>`
            : html`<button type="button" class="${i.perigo ? 'perigo' : ''}" data-acao="${i.acao}" data-id="${r.id}"><i class="ph ${i.icone}" aria-hidden="true"></i>${i.texto}</button>`))}</div></details>`;
}

const linhaConfirmada = (r) => html`<tr id="reserva-${r.id}">
    <td class="num"><strong>${r.assento ?? '-'}</strong></td>
    <td>${celulaPassageiro(r)}</td>
    <td class="num">${documentoTexto(r.passageiro)}</td>
    <td>${r.cidade_embarque || html`<span class="muted">Não informado</span>`}</td>
    <td>${etiquetaPagamento(r.status_pagamento)}${r.ultimo_pagamento ? html`<div class="sub">último em ${dataBr(r.ultimo_pagamento)}</div>` : ''}</td>
    <td class="direita num">${brl(r.pago_centavos)}<div class="sub">de ${brl(r.valor_total_centavos)}</div></td>
    <td class="direita"><div class="acoes-linha">
        <button type="button" class="btn btn-neutro btn-pequeno" data-acao="pagamento" data-id="${r.id}"><i class="ph ph-currency-circle-dollar" aria-hidden="true"></i>Pagamento</button>
        ${r.saldo_centavos > 0 && r.valor_total_centavos > 0
            ? html`<button type="button" class="btn btn-ok btn-pequeno" data-acao="quitar" data-id="${r.id}"><i class="ph ph-check" aria-hidden="true"></i>Quitar</button>`
            : ''}
        ${menuMais(r, [
            { acao: 'editar-reserva', icone: 'ph-pencil-simple', texto: 'Editar valor e embarque' },
            { acao: 'assento', icone: 'ph-armchair', texto: 'Trocar de assento' },
            { acao: 'transferir', icone: 'ph-arrows-left-right', texto: 'Transferir para outra van' },
            { acao: 'espera', icone: 'ph-hourglass-medium', texto: 'Mandar para a lista de espera' },
            '---',
            { acao: 'cancelar', icone: 'ph-x-circle', texto: 'Cancelar reserva', perigo: true },
        ])}
    </div></td></tr>`;

const linhaEspera = (r, temVaga) => html`<tr id="reserva-${r.id}">
    <td class="num"><strong>${r.posicao_espera}º</strong></td>
    <td>${celulaPassageiro(r)}</td>
    <td class="num">${documentoTexto(r.passageiro)}</td>
    <td>${etiquetaPagamento(r.status_pagamento)}</td>
    <td class="direita"><div class="acoes-linha">
        <button type="button" class="btn btn-ok btn-pequeno" data-acao="confirmar" data-id="${r.id}" ${temVaga ? '' : 'disabled'}
            title="${temVaga ? 'Confirma o passageiro e dá o primeiro assento livre' : 'A van está lotada. Libere um assento primeiro.'}">
            <i class="ph ph-check" aria-hidden="true"></i>Confirmar na van</button>
        <button type="button" class="btn btn-neutro btn-pequeno" data-acao="pagamento" data-id="${r.id}"><i class="ph ph-currency-circle-dollar" aria-hidden="true"></i>Pagamento</button>
        ${menuMais(r, [
            { acao: 'editar-reserva', icone: 'ph-pencil-simple', texto: 'Editar valor e embarque' },
            { acao: 'transferir', icone: 'ph-arrows-left-right', texto: 'Transferir para outra van' },
            '---',
            { acao: 'cancelar', icone: 'ph-x-circle', texto: 'Tirar da lista (cancelar)', perigo: true },
        ])}
    </div></td></tr>`;

const linhaCancelada = (r) => html`<tr>
    <td>${celulaPassageiro(r)}</td>
    <td class="num">${documentoTexto(r.passageiro)}</td>
    <td class="direita num">${brl(r.pago_centavos)}</td>
    <td class="direita"><button type="button" class="btn btn-neutro btn-pequeno" data-acao="reativar" data-passageiro="${r.passageiro.id}">
        <i class="ph ph-arrow-counter-clockwise" aria-hidden="true"></i>Reativar</button></td></tr>`;

function mapaDeAssentos(v) {
    const porAssento = new Map(v.confirmadas.map((r) => [r.assento, r]));
    const assentos = Array.from({ length: v.capacidade }, (_, i) => i + 1);
    return html`<div class="assentos" role="list">${assentos.map((n) => {
        const r = porAssento.get(n);
        return r
            ? html`<button type="button" class="assento taken ${r.status_pagamento}" role="listitem" data-acao="ir-para" data-id="${r.id}"
                    aria-label="Assento ${n}, ${r.passageiro.nome}, pagamento ${r.status_pagamento}">
                    <span class="numero-assento">${n}</span><span class="quem">${primeiroNome(r.passageiro.nome)}</span></button>`
            : html`<button type="button" class="assento livre" role="listitem" data-acao="adicionar" data-assento="${n}" aria-label="Assento ${n} livre. Adicionar passageiro">
                    <span class="numero-assento">${n}</span><span class="quem">Livre</span></button>`;
    })}</div>
    <div class="legenda" aria-hidden="true">
        <span><i class="ok"></i>Pago</span><span><i class="parcial"></i>Parcial</span><span><i class="pendente"></i>Pendente</span>
    </div>`;
}

export async function renderizar(raiz, ctx) {
    const [id] = ctx.ids;
    const v = await api.get(`/api/veiculos/${id}`);
    const evento = await api.get(`/api/eventos/${v.evento_id}`);
    ctx.titulo(`${v.nome} (${evento.titulo})`);
    raiz._dados = { v, evento };

    const todas = [...v.confirmadas, ...v.espera, ...v.canceladas];
    const temVaga = v.livres > 0;
    raiz.innerHTML = html`
        <a class="voltar" href="#/eventos/${evento.id}"><i class="ph ph-arrow-left" aria-hidden="true"></i>${evento.titulo}</a>
        <div class="cabecalho">
            <div class="titulo">
                <h1>${v.nome}</h1>
                <p>${TIPOS_VEICULO[v.tipo]}${v.placa ? ` · placa ${v.placa}` : ''} · ${evento.data_texto}</p>
                <div class="mini-ficha">
                    ${v.contato
                        ? html`<span><i class="ph ph-steering-wheel" aria-hidden="true"></i>${v.contato.nome}
                            ${v.contato.telefone
                                ? html`· ${linkWhatsApp(v.contato.telefone)
                                    ? html`<a href="${linkWhatsApp(v.contato.telefone)}" target="_blank" rel="noopener noreferrer">${v.contato.telefone}</a>`
                                    : v.contato.telefone}`
                                : ''}</span>`
                        : html`<span class="muted"><i class="ph ph-user-minus" aria-hidden="true"></i>Sem motorista ou empresa ligada</span>`}
                    <span><i class="ph ph-tag" aria-hidden="true"></i>Valor padrão ${v.valor_padrao_centavos ? brl(v.valor_padrao_centavos) : 'não definido'}</span>
                </div>
                ${v.observacoes ? html`<p class="muted">${v.observacoes}</p>` : ''}
            </div>
            <div class="acoes">
                <button class="btn btn-primario" type="button" data-acao="adicionar"><i class="ph ph-user-plus" aria-hidden="true"></i>Adicionar passageiro</button>
                <button class="btn btn-neutro" type="button" data-acao="editar-van"><i class="ph ph-pencil-simple" aria-hidden="true"></i>Editar van</button>
                <button class="btn btn-perigo btn-icone" type="button" data-acao="apagar-van" aria-label="Apagar van"><i class="ph ph-trash" aria-hidden="true"></i></button>
            </div>
        </div>

        <div class="numeros" role="list">
            <div class="numero" role="listitem"><span class="rotulo-num">Assentos</span><strong>${v.confirmados}<small> de ${v.capacidade}</small></strong>${barraSimples(v.confirmados, v.capacidade)}</div>
            <div class="numero" role="listitem"><span class="rotulo-num">Livres</span><strong>${v.livres}</strong><small>${v.livres ? 'ainda cabem passageiros' : 'van lotada'}</small></div>
            <div class="numero" role="listitem"><span class="rotulo-num">Lista de espera</span><strong>${v.em_espera}</strong><small>${v.em_espera ? 'aguardando vaga' : 'ninguém esperando'}</small></div>
            <div class="numero destaque" role="listitem"><span class="rotulo-num">A receber</span><strong>${brl(v.a_receber_centavos)}</strong><small>já recebido: ${brl(v.pago_centavos)}</small></div>
        </div>

        <section class="secao" aria-labelledby="t-mapa">
            <div class="secao-topo"><h2 id="t-mapa">Mapa de assentos</h2><span class="muted">Toque num assento livre para adicionar alguém, ou num ocupado para ir até a linha dele.</span></div>
            <div class="painel"><div class="painel-corpo">${mapaDeAssentos(v)}</div></div>
        </section>

        <section class="secao" aria-labelledby="t-pass">
            <div class="secao-topo"><h2 id="t-pass">Passageiros (${v.confirmadas.length})</h2></div>
            ${v.confirmadas.length
                ? html`<div class="tabela-rolagem larga"><table>
                    <caption class="sr-only">Passageiros confirmados nesta van</caption>
                    <thead><tr><th>Assento</th><th>Passageiro</th><th>Documento</th><th>Embarque</th><th>Pagamento</th><th class="direita">Pago</th><th><span class="sr-only">Ações</span></th></tr></thead>
                    <tbody>${v.confirmadas.map(linhaConfirmada)}</tbody></table></div>`
                : estadoVazio('ph-user-plus', 'Nenhum passageiro nesta van ainda', 'Adicione quem já está confirmado. Se a van lotar, os próximos vão para a lista de espera.',
                    html`<button class="btn btn-primario" type="button" data-acao="adicionar"><i class="ph ph-user-plus" aria-hidden="true"></i>Adicionar passageiro</button>`)}
        </section>

        <section class="secao" aria-labelledby="t-espera">
            <div class="secao-topo"><h2 id="t-espera">Lista de espera (${v.espera.length})</h2></div>
            ${v.espera.length
                ? html`<div class="tabela-rolagem larga"><table>
                    <caption class="sr-only">Pessoas aguardando vaga nesta van, na ordem de chegada</caption>
                    <thead><tr><th>Posição</th><th>Passageiro</th><th>Documento</th><th>Pagamento</th><th><span class="sr-only">Ações</span></th></tr></thead>
                    <tbody>${v.espera.map((r) => linhaEspera(r, temVaga))}</tbody></table></div>`
                : html`<div class="painel"><div class="painel-corpo muted">Ninguém na lista de espera. Quando a van lotar, quem for adicionado depois entra aqui, na ordem de chegada.</div></div>`}
        </section>

        ${v.canceladas.length ? html`<section class="secao">
            <details class="painel"><summary class="painel-corpo"><strong>Cancelados (${v.canceladas.length})</strong>
                <span class="muted"> · saíram da van, mas o histórico de pagamentos fica guardado</span></summary>
                <div class="tabela-rolagem"><table>
                    <thead><tr><th>Passageiro</th><th>Documento</th><th class="direita">Pago</th><th><span class="sr-only">Ações</span></th></tr></thead>
                    <tbody>${v.canceladas.map(linhaCancelada)}</tbody></table></div></details></section>` : ''}
    `.toString();
    raiz._mapa = new Map(todas.map((r) => [String(r.id), r]));
}

// ------------------------------------------------------------------ ações
export function ligar(raiz, ctx) {
    const { v, evento } = raiz._dados;
    const reserva = (el) => raiz._mapa.get(String(el.dataset.id));
    const depois = (mensagem) => { if (mensagem) toast(mensagem); ctx.recarregar(); };
    const falhar = (erro) => toast(erro instanceof ApiError ? erro.message : 'Algo deu errado.', 'erro');

    raiz.addEventListener('click', (ev) => {
        raiz.querySelectorAll('.menu-mais[open]').forEach((d) => { if (!d.contains(ev.target)) d.removeAttribute('open'); });
    });

    ouvirAcoes(raiz, 'click', async (acao, el) => {
        el.closest('details')?.removeAttribute('open');
        try {
            switch (acao) {
                case 'adicionar': return dialogAdicionar(v, evento, { assento: Number(el.dataset.assento) || null }, depois);
                case 'ver-passageiro': return abrirDetalhe(Number(el.dataset.passageiro), ctx.recarregar);
                case 'ir-para': {
                    const linha = raiz.querySelector(`#reserva-${el.dataset.id}`);
                    if (!linha) return;
                    linha.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    linha.classList.add('destacada');
                    setTimeout(() => linha.classList.remove('destacada'), 2200);
                    return;
                }
                case 'pagamento': return dialogPagamento(reserva(el), depois);
                case 'quitar': return dialogPagamento(reserva(el), depois, 'completo');
                case 'editar-reserva': return dialogEditarReserva(reserva(el), evento, depois);
                case 'assento': return dialogAssento(reserva(el), v, depois);
                case 'transferir': return dialogTransferir(reserva(el), v, evento, depois);
                case 'editar-van': return dialogEditarVan(v, depois);
                case 'confirmar': {
                    const r = reserva(el);
                    await api.post(`/api/reservas/${r.id}/confirmar`);
                    return depois(`${r.passageiro.nome} confirmado na van`);
                }
                case 'espera': {
                    const r = reserva(el);
                    const sim = await confirmar({
                        titulo: 'Mandar para a lista de espera?',
                        mensagem: `${r.passageiro.nome} perde o assento ${r.assento} e vai para o fim da fila. Os pagamentos continuam registrados.`,
                        rotulo: 'Mandar para a espera',
                    });
                    if (!sim) return;
                    await api.post(`/api/reservas/${r.id}/espera`);
                    return depois(`${r.passageiro.nome} foi para a lista de espera`);
                }
                case 'cancelar': {
                    const r = reserva(el);
                    const sim = await confirmar({
                        titulo: 'Cancelar esta reserva?',
                        mensagem: `${r.passageiro.nome} sai da van e o assento fica livre. Os pagamentos já registrados continuam no histórico.`,
                        rotulo: 'Cancelar reserva',
                        perigo: true,
                    });
                    if (!sim) return;
                    await api.post(`/api/reservas/${r.id}/cancelar`);
                    return depois('Reserva cancelada');
                }
                case 'reativar': {
                    await api.post(`/api/veiculos/${v.id}/reservas`, { passageiro_id: Number(el.dataset.passageiro) });
                    return depois('Passageiro reativado');
                }
                case 'apagar-van': {
                    const sim = await confirmar({
                        titulo: `Apagar ${v.nome}?`,
                        mensagem: 'A van some da viagem. Só é possível se não houver ninguém nela (nem na lista de espera).',
                        rotulo: 'Apagar van',
                        perigo: true,
                    });
                    if (!sim) return;
                    await api.del(`/api/veiculos/${v.id}`);
                    toast('Van apagada');
                    location.hash = `#/eventos/${evento.id}`;
                    return;
                }
                default: return;
            }
        } catch (erro) {
            falhar(erro);
        }
    });
}

// ------------------------------------------------------------------ janelas
function dialogAdicionar(v, evento, { assento }, depois) {
    const ocupados = new Set(v.confirmadas.map((r) => r.assento));
    const livres = Array.from({ length: v.capacidade }, (_, i) => i + 1).filter((n) => !ocupados.has(n));
    janela({
        titulo: `Adicionar à ${v.nome}`,
        botao: 'Adicionar',
        conteudo: html`
            <p class="muted">${v.livres
                ? `${plural(v.livres, 'assento livre', 'assentos livres')}.`
                : 'A van está lotada: quem for adicionado entra na lista de espera.'}</p>
            <fieldset class="campo"><legend>Quem vai</legend>
                <div class="segmentos" role="group" aria-label="Passageiro já cadastrado ou novo">
                    <button type="button" data-modo="existente" aria-pressed="true">Já cadastrado</button>
                    <button type="button" data-modo="novo" aria-pressed="false">Cadastrar novo</button>
                </div></fieldset>
            <div data-painel="existente" class="campo">
                <label for="p-busca">Buscar pelo nome ou documento</label>
                <input type="search" id="p-busca" placeholder="Digite pelo menos 2 letras…" autocomplete="off">
                <div class="resultados" id="p-resultados" role="radiogroup" aria-label="Passageiros encontrados" aria-live="polite"></div>
                <input type="hidden" name="escolhido" id="p-escolhido">
            </div>
            <div data-painel="novo" class="grade-campos" hidden>
                <div class="campo largo"><label for="n-nome">Nome completo</label><input type="text" id="n-nome" name="n_nome" autocomplete="off" maxlength="120"></div>
                <div class="campo"><label for="n-tipo">Documento</label>
                    <select id="n-tipo" name="n_tipo"><option value="cpf">CPF</option><option value="rg">RG</option></select></div>
                <div class="campo"><label for="n-numero">Número</label><input type="text" id="n-numero" name="n_numero" autocomplete="off" inputmode="text" maxlength="30"></div>
            </div>
            <div class="grade-campos">
                <div class="campo"><label for="a-cidade">Cidade de embarque</label>
                    <select id="a-cidade" name="cidade"><option value="">Não informada</option>
                        ${evento.cidades.map((c) => html`<option>${c}</option>`)}</select></div>
                <div class="campo"><label for="a-valor">Valor total (R$)</label>
                    <input type="text" id="a-valor" name="valor" inputmode="decimal" autocomplete="off"
                        value="${v.valor_padrao_centavos ? reaisParaCampo(v.valor_padrao_centavos) : ''}" placeholder="0,00"></div>
                <div class="campo"><label for="a-assento">Assento</label>
                    <select id="a-assento" name="assento"><option value="">Automático (primeiro livre)</option>
                        ${livres.map((n) => html`<option value="${n}" ${n === assento ? 'selected' : ''}>${n}</option>`)}</select></div>
                <div class="campo"><span class="rotulo">Lista de espera</span>
                    <label class="check"><input type="checkbox" name="espera" ${v.livres ? '' : 'checked disabled'}>
                        <span>${v.livres ? 'Colocar na lista de espera, mesmo com vaga' : 'Van lotada: entra na lista de espera'}</span></label></div>
            </div>`,
        aoAbrir: (dlg) => prepararBuscaDePassageiro(dlg),
        aoEnviar: async (dados, dlg) => {
            const modo = dlg.querySelector('[data-modo][aria-pressed="true"]').dataset.modo;
            const corpo = {
                cidade_embarque: dados.get('cidade') || null,
                assento: dados.get('assento') ? Number(dados.get('assento')) : null,
                lista_de_espera: dados.get('espera') === 'on',
            };
            const texto = String(dados.get('valor') || '').trim();
            if (texto) {
                const valor = lerReais(texto);
                if (Number.isNaN(valor)) throw erroDeTela('Informe um valor válido, como 150,00.');
                corpo.valor_total_centavos = valor;
            }
            if (modo === 'existente') {
                const escolhido = dados.get('escolhido') || dados.get('p-radio');
                if (!escolhido) throw erroDeTela('Escolha um passageiro da lista ou cadastre um novo.');
                corpo.passageiro_id = Number(escolhido);
            } else {
                if (!String(dados.get('n_nome')).trim()) throw erroDeTela('Informe o nome do passageiro.');
                corpo.novo_passageiro = {
                    nome: String(dados.get('n_nome')).trim(),
                    documento_tipo: dados.get('n_tipo'),
                    documento_numero: String(dados.get('n_numero')).trim(),
                };
            }
            try {
                const r = await api.post(`/api/veiculos/${v.id}/reservas`, corpo);
                depois(r.situacao === 'espera'
                    ? `${r.passageiro.nome} entrou na lista de espera (${r.posicao_espera}º)`
                    : `${r.passageiro.nome} adicionado no assento ${r.assento}`);
            } catch (erro) {
                const existente = erro instanceof ApiError && erro.detalhe && erro.detalhe.passageiro_id;
                if (!existente) throw erro;
                // o documento já existe: oferece usar quem já está cadastrado
                dlg.mostrarErro(`${erro.message} Use o cadastro que já existe.`);
                const area = dlg.querySelector('[data-erro-geral]');
                const botao = document.createElement('button');
                botao.type = 'button';
                botao.className = 'btn btn-neutro btn-pequeno';
                botao.textContent = 'Usar esse passageiro';
                botao.addEventListener('click', () => {
                    dlg.querySelector('#p-escolhido').value = existente;
                    dlg.querySelector('[data-modo="existente"]').click();
                    dlg.querySelector('#p-resultados').innerHTML = html`<p class="muted">Passageiro já cadastrado selecionado. Toque em Adicionar.</p>`.toString();
                    dlg.mostrarErro('');
                    botao.remove();
                });
                area.after(botao);
                return false;
            }
        },
    });
}

function prepararBuscaDePassageiro(dlg) {
    const botoes = dlg.querySelectorAll('[data-modo]');
    botoes.forEach((b) => b.addEventListener('click', () => {
        botoes.forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        dlg.querySelector('[data-painel="existente"]').hidden = b.dataset.modo !== 'existente';
        dlg.querySelector('[data-painel="novo"]').hidden = b.dataset.modo !== 'novo';
        (b.dataset.modo === 'novo' ? dlg.querySelector('#n-nome') : dlg.querySelector('#p-busca')).focus();
    }));
    const resultados = dlg.querySelector('#p-resultados');
    const escolhido = dlg.querySelector('#p-escolhido');
    const buscar = debounce(async (ev) => {
        const q = ev.target.value.trim();
        escolhido.value = '';
        if (q.length < 2) { resultados.innerHTML = ''; return; }
        try {
            const lista = await api.get('/api/passageiros', { q, limite: 12 });
            resultados.innerHTML = lista.length
                ? lista.map((p) => html`<div class="opcao"><input type="radio" name="p-radio" id="pr-${p.id}" value="${p.id}">
                    <label for="pr-${p.id}"><span><strong>${p.nome}</strong><br><span class="muted">${idPassageiro(p.id)} · ${documentoTexto(p)}</span></span></label></div>`).join('')
                : html`<p class="muted">Ninguém encontrado. Use “Cadastrar novo”.</p>`.toString();
        } catch (erro) {
            resultados.innerHTML = html`<p class="erro">${erro.message}</p>`.toString();
        }
    });
    dlg.querySelector('#p-busca').addEventListener('input', buscar);
}

function dialogPagamento(r, depois, modoInicial = 'parcial') {
    const saldo = r.saldo_centavos;
    const quitado = saldo <= 0 && r.valor_total_centavos > 0;
    const semValor = r.valor_total_centavos <= 0;
    janela({
        titulo: `Pagamento de ${r.passageiro.nome}`,
        botao: quitado || semValor ? null : 'Registrar pagamento',
        conteudo: html`
            <div class="resumo-pagamento">
                <div><span>Valor total</span><strong>${brl(r.valor_total_centavos)}</strong></div>
                <div><span>Já pago</span><strong>${brl(r.pago_centavos)}</strong></div>
                <div><span>Falta pagar</span><strong>${brl(saldo)}</strong></div>
            </div>
            ${semValor ? html`<p class="alerta erro"><i class="ph ph-warning" aria-hidden="true"></i><span>Esta reserva ainda não tem valor total. Use “Editar valor e embarque” antes de registrar pagamentos.</span></p>` : ''}
            ${quitado ? html`<p class="alerta sucesso"><i class="ph-fill ph-check-circle" aria-hidden="true"></i><span>Pagamento completo. Nada a receber.</span></p>` : ''}
            ${!quitado && !semValor ? html`
            <fieldset class="campo"><legend>Tipo de pagamento</legend>
                <div class="opcoes">
                    <div class="opcao"><input type="radio" name="modo" id="m-parcial" value="parcial" ${modoInicial === 'parcial' ? 'checked' : ''}>
                        <label for="m-parcial"><span><strong>Parcial</strong><br><span class="muted">Informe quanto foi pago agora</span></span></label></div>
                    <div class="opcao"><input type="radio" name="modo" id="m-completo" value="completo" ${modoInicial === 'completo' ? 'checked' : ''}>
                        <label for="m-completo"><span><strong>Completo</strong><br><span class="muted">Quita o saldo de ${brl(saldo)}</span></span></label></div>
                </div></fieldset>
            <div class="grade-campos">
                <div class="campo"><label for="p-data">Data do pagamento</label>
                    <input type="date" id="p-data" name="data" value="${hojeISO()}" max="${hojeISO()}" required></div>
                <div class="campo"><label for="p-valor">Valor pago (R$)</label>
                    <input type="text" id="p-valor" name="valor" inputmode="decimal" autocomplete="off" placeholder="0,00"></div>
                <div class="campo largo"><label for="p-obs">Observação (opcional)</label>
                    <input type="text" id="p-obs" name="observacao" maxlength="300" autocomplete="off" placeholder="Ex.: Pix, dinheiro, comprovante enviado"></div>
            </div>` : ''}
            ${r.pagamentos.length ? html`<div class="campo"><span class="rotulo">Histórico</span>
                <ul class="historico">${r.pagamentos.map((p) => html`<li>
                    <span><strong class="num">${brl(p.valor_centavos)}</strong> em ${dataBr(p.data)}
                        <span class="etiqueta ${p.tipo === 'total' ? 'ok' : 'atencao'}">${p.tipo === 'total' ? 'Completo' : 'Parcial'}</span></span>
                    <span class="muted">${p.registrado_por}${p.observacao ? ` · ${p.observacao}` : ''}</span>
                    <button type="button" class="btn btn-perigo btn-pequeno" data-desfazer="${p.id}">Desfazer</button></li>`)}</ul>
                <span class="dica">“Desfazer” serve para corrigir um lançamento errado.</span></div>` : ''}`,
        aoAbrir: (dlg) => {
            const valor = dlg.querySelector('#p-valor');
            const modos = dlg.querySelectorAll('[name="modo"]');
            const ajustar = () => {
                const completo = dlg.querySelector('[name="modo"]:checked')?.value === 'completo';
                if (!valor) return;
                valor.disabled = completo;
                valor.value = completo ? reaisParaCampo(saldo) : '';
            };
            modos.forEach((m) => m.addEventListener('change', ajustar));
            ajustar();
            dlg.querySelectorAll('[data-desfazer]').forEach((b) => b.addEventListener('click', async () => {
                const sim = await confirmar({ titulo: 'Desfazer este pagamento?', mensagem: 'O lançamento some e o saldo volta a ser calculado.', rotulo: 'Desfazer', perigo: true });
                if (!sim) return;
                try {
                    await api.del(`/api/pagamentos/${b.dataset.desfazer}`);
                    dlg.close();
                    depois('Pagamento desfeito');
                } catch (erro) {
                    dlg.mostrarErro(erro.message);
                }
            }));
        },
        aoEnviar: async (dados) => {
            const modo = dados.get('modo');
            const base = { data: dados.get('data') || null, observacao: String(dados.get('observacao') || '').trim() || null };
            if (modo === 'completo') {
                await api.post(`/api/reservas/${r.id}/quitar`, base);
                return depois(`${r.passageiro.nome} quitou o pagamento`);
            }
            const valor = lerReais(dados.get('valor'));
            if (Number.isNaN(valor) || valor <= 0) throw erroDeTela('Informe o valor pago, como 50,00.');
            if (valor > saldo) throw erroDeTela(`O valor passa do que falta pagar (${brl(saldo)}).`);
            await api.post(`/api/reservas/${r.id}/pagamentos`, { ...base, valor_centavos: valor });
            return depois(valor === saldo ? `${r.passageiro.nome} quitou o pagamento` : 'Pagamento parcial registrado');
        },
    });
}

function dialogEditarReserva(r, evento, depois) {
    janela({
        titulo: `Reserva de ${r.passageiro.nome}`,
        conteudo: html`
            <div class="grade-campos">
                <div class="campo"><label for="e-valor">Valor total (R$)</label>
                    <input type="text" id="e-valor" name="valor" inputmode="decimal" autocomplete="off" value="${reaisParaCampo(r.valor_total_centavos)}">
                    <span class="dica">Já foram pagos ${brl(r.pago_centavos)}. O total não pode ficar abaixo disso.</span></div>
                <div class="campo"><label for="e-cidade">Cidade de embarque</label>
                    <select id="e-cidade" name="cidade"><option value="">Não informada</option>
                        ${evento.cidades.map((c) => html`<option ${c === r.cidade_embarque ? 'selected' : ''}>${c}</option>`)}
                        ${r.cidade_embarque && !evento.cidades.includes(r.cidade_embarque) ? html`<option selected>${r.cidade_embarque}</option>` : ''}</select></div>
                <div class="campo largo"><label for="e-obs">Observações</label>
                    <textarea id="e-obs" name="observacoes" maxlength="500">${r.observacoes || ''}</textarea></div>
            </div>`,
        aoEnviar: async (dados) => {
            const valor = lerReais(dados.get('valor'));
            if (Number.isNaN(valor)) throw erroDeTela('Informe um valor válido, como 150,00.');
            await api.patch(`/api/reservas/${r.id}`, {
                valor_total_centavos: valor,
                cidade_embarque: dados.get('cidade') || null,
                observacoes: String(dados.get('observacoes')).trim() || null,
            });
            depois('Reserva atualizada');
        },
    });
}

function dialogAssento(r, v, depois) {
    const ocupados = new Set(v.confirmadas.filter((x) => x.id !== r.id).map((x) => x.assento));
    const livres = Array.from({ length: v.capacidade }, (_, i) => i + 1).filter((n) => !ocupados.has(n));
    janela({
        titulo: `Assento de ${r.passageiro.nome}`,
        conteudo: html`<div class="campo"><label for="s-assento">Novo assento</label>
            <select id="s-assento" name="assento">${livres.map((n) => html`<option value="${n}" ${n === r.assento ? 'selected' : ''}>${n}${n === r.assento ? ' (atual)' : ''}</option>`)}</select>
            <span class="dica">Só aparecem os assentos livres.</span></div>`,
        aoEnviar: async (dados) => {
            await api.patch(`/api/reservas/${r.id}`, { assento: Number(dados.get('assento')) });
            depois('Assento trocado');
        },
    });
}

function dialogTransferir(r, v, evento, depois) {
    const outras = evento.lista_de_veiculos.filter((x) => x.id !== v.id);
    if (!outras.length) {
        toast('Não há outra van nesta viagem. Cadastre uma na página da viagem.', 'erro');
        return;
    }
    janela({
        titulo: `Transferir ${r.passageiro.nome}`,
        botao: 'Transferir',
        conteudo: html`
            <div class="campo"><label for="t-van">Para qual van</label>
                <select id="t-van" name="van">${outras.map((x) => html`<option value="${x.id}">${x.nome} (${x.livres ? plural(x.livres, 'livre', 'livres') : 'lotada'})</option>`)}</select></div>
            ${r.situacao === 'confirmado' ? html`<label class="check"><input type="checkbox" name="espera">
                <span>Se a van de destino estiver lotada, entrar na lista de espera dela</span></label>` : ''}`,
        aoEnviar: async (dados) => {
            await api.post(`/api/reservas/${r.id}/transferir`, {
                veiculo_id: Number(dados.get('van')),
                entrar_na_espera_se_lotado: dados.get('espera') === 'on',
            });
            depois(`${r.passageiro.nome} foi transferido`);
        },
    });
}

function dialogEditarVan(v, depois) {
    api.get('/api/contatos', { somente_ativos: true }).then((contatos) => {
        const motoristas = contatos.filter((c) => ['motorista', 'empresa_fretamento'].includes(c.categoria));
        janela({
            titulo: `Editar ${v.nome}`,
            conteudo: html`
                <div class="grade-campos">
                    <div class="campo"><label for="ev-nome">Nome</label><input type="text" id="ev-nome" name="nome" value="${v.nome}" maxlength="60" required></div>
                    <div class="campo"><label for="ev-tipo">Tipo</label>
                        <select id="ev-tipo" name="tipo">${Object.entries(TIPOS_VEICULO).map(([k, t]) => html`<option value="${k}" ${k === v.tipo ? 'selected' : ''}>${t}</option>`)}</select></div>
                    <div class="campo"><label for="ev-assentos">Quantidade de assentos</label>
                        <input type="number" id="ev-assentos" name="capacidade" min="1" max="80" inputmode="numeric" value="${v.capacidade}" required>
                        <span class="dica">${v.confirmados} ocupados agora.</span></div>
                    <div class="campo"><label for="ev-valor">Valor padrão por pessoa (R$)</label>
                        <input type="text" id="ev-valor" name="valor" inputmode="decimal" autocomplete="off" value="${v.valor_padrao_centavos ? reaisParaCampo(v.valor_padrao_centavos) : ''}">
                        <span class="dica">Vale para quem for adicionado depois.</span></div>
                    <div class="campo"><label for="ev-placa">Placa</label><input type="text" id="ev-placa" name="placa" maxlength="10" value="${v.placa || ''}" autocomplete="off"></div>
                    <div class="campo"><label for="ev-contato">Motorista ou empresa</label>
                        <select id="ev-contato" name="contato_id"><option value="">Nenhum</option>
                            ${motoristas.map((c) => html`<option value="${c.id}" ${v.contato && v.contato.id === c.id ? 'selected' : ''}>${c.nome}</option>`)}</select></div>
                    <div class="campo largo"><label for="ev-obs">Observações</label><textarea id="ev-obs" name="observacoes" maxlength="1000">${v.observacoes || ''}</textarea></div>
                </div>`,
            aoEnviar: async (dados) => {
                const texto = String(dados.get('valor') || '').trim();
                const valor = texto ? lerReais(texto) : 0;
                if (Number.isNaN(valor)) throw erroDeTela('Informe um valor válido, como 150,00.');
                await api.patch(`/api/veiculos/${v.id}`, {
                    nome: dados.get('nome').trim(),
                    tipo: dados.get('tipo'),
                    capacidade: Number(dados.get('capacidade')),
                    valor_padrao_centavos: valor,
                    placa: dados.get('placa').trim() || null,
                    contato_id: dados.get('contato_id') ? Number(dados.get('contato_id')) : null,
                    observacoes: dados.get('observacoes').trim() || null,
                });
                depois('Van atualizada');
            },
        });
    }).catch((erro) => toast(erro.message, 'erro'));
}

