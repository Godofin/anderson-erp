import { api } from '../api.js';
import { cartaoVan } from '../componentes.js';
import {
    TIPOS_VEICULO, barraSimples, brl, confirmar, erroDeTela, estadoVazio, html, janela, lerReais, plural, quandoFalta, toast,
} from '../ui.js';

export async function renderizar(raiz, ctx) {
    const [evento] = ctx.ids;
    const e = await api.get(`/api/eventos/${evento}`);
    ctx.titulo(e.titulo);
    raiz.innerHTML = html`
        <a class="voltar" href="#/eventos"><i class="ph ph-arrow-left" aria-hidden="true"></i>Eventos e vans</a>
        <div class="cabecalho">
            <div class="titulo">
                <h1>${e.titulo}</h1>
                <p>${e.data_texto}${e.data_inicio ? ` · ${quandoFalta(e.data_inicio)}` : ''}</p>
                <div class="chips">${e.cidades.map((c) => html`<span class="etiqueta neutra"><i class="ph ph-map-pin" aria-hidden="true"></i>${c}</span>`)}
                    ${!e.ativo ? html`<span class="etiqueta atencao"><i class="ph ph-eye-slash" aria-hidden="true"></i>Fora do site</span>` : ''}</div>
            </div>
            <div class="acoes">
                <a class="btn btn-neutro" href="#/eventos/${e.id}/editar"><i class="ph ph-pencil-simple" aria-hidden="true"></i>Editar evento</a>
                <button class="btn btn-neutro" type="button" data-acao="visibilidade" data-ativo="${e.ativo}">
                    <i class="ph ${e.ativo ? 'ph-eye-slash' : 'ph-eye'}" aria-hidden="true"></i>${e.ativo ? 'Tirar do site' : 'Publicar no site'}</button>
                <button class="btn btn-primario" type="button" data-acao="nova-van"><i class="ph ph-plus" aria-hidden="true"></i>Nova van ou ônibus</button>
            </div>
        </div>

        <div class="numeros" role="list">
            <div class="numero" role="listitem"><span class="rotulo-num">Vans e ônibus</span><strong>${e.veiculos}</strong><small>${e.assentos} assentos no total</small></div>
            <div class="numero" role="listitem"><span class="rotulo-num">Confirmados</span><strong>${e.confirmados}<small> de ${e.assentos}</small></strong>${e.assentos ? barraSimples(e.confirmados, e.assentos) : ''}</div>
            <div class="numero" role="listitem"><span class="rotulo-num">Lista de espera</span><strong>${e.em_espera}</strong><small>somando todas as vans</small></div>
            <div class="numero destaque" role="listitem"><span class="rotulo-num">A receber</span><strong>${brl(e.a_receber_centavos)}</strong><small>já recebido: ${brl(e.pago_centavos)}</small></div>
        </div>

        <section class="secao" aria-labelledby="t-vans">
            <div class="secao-topo"><h2 id="t-vans">Vans e ônibus</h2></div>
            ${e.lista_de_veiculos.length
                ? html`<div class="grade-vans">${e.lista_de_veiculos.map(cartaoVan)}</div>`
                : estadoVazio('ph-bus', 'Nenhuma van cadastrada nesta viagem',
                    'Cadastre a primeira van ou ônibus, com a quantidade de assentos. Depois é só colocar os passageiros nela.',
                    html`<button class="btn btn-primario" type="button" data-acao="nova-van"><i class="ph ph-plus" aria-hidden="true"></i>Cadastrar a primeira van</button>`)}
        </section>

        <section class="secao" aria-labelledby="t-evento">
            <div class="secao-topo"><h2 id="t-evento">Evento no site</h2></div>
            <div class="painel"><div class="painel-corpo linha-aviso">
                <p>${e.ativo ? 'Este evento aparece no site.' : 'Este evento está fora do site.'}
                    ${e.veiculos ? ' Para apagar, antes apague as vans dele ou apenas tire do site.' : ' Apagar remove do site e do ERP, sem volta.'}</p>
                <button class="btn btn-perigo" type="button" data-acao="apagar-evento"><i class="ph ph-trash" aria-hidden="true"></i>Apagar evento</button>
            </div></div>
        </section>`.toString();
    raiz.dataset.evento = e.id;
    raiz.dataset.titulo = e.titulo;
    raiz.dataset.veiculos = e.veiculos;
    raiz.dataset.cidades = JSON.stringify(e.cidades);
}

export function ligar(raiz, ctx) {
    const eventoId = Number(raiz.dataset.evento);
    raiz.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-acao="nova-van"]')) abrirNovaVan(eventoId, ctx);
        const visib = ev.target.closest('[data-acao="visibilidade"]');
        if (visib) mudarVisibilidade(eventoId, visib.dataset.ativo !== 'true', ctx);
        if (ev.target.closest('[data-acao="apagar-evento"]')) apagarEvento(eventoId, raiz.dataset.titulo, Number(raiz.dataset.veiculos));
    });
}

async function mudarVisibilidade(eventoId, publicar, ctx) {
    const sim = await confirmar({
        titulo: publicar ? 'Publicar este evento no site?' : 'Tirar este evento do site?',
        mensagem: publicar
            ? 'O evento passa a aparecer no site agora, para todos os visitantes.'
            : 'O evento some do site. As vans e os passageiros daqui continuam guardados.',
        rotulo: publicar ? 'Publicar no site' : 'Tirar do site',
    });
    if (!sim) return;
    try {
        await api.patch(`/api/eventos/${eventoId}/visibilidade`, { ativo: publicar });
        toast(publicar ? 'Evento publicado no site' : 'Evento fora do site');
        ctx.recarregar();
    } catch (erro) {
        toast(erro.message, 'erro');
    }
}

async function apagarEvento(eventoId, titulo, vans) {
    if (vans) {
        toast(`Este evento tem ${plural(vans, 'van', 'vans')} no ERP. Tire do site em vez de apagar.`, 'erro');
        return;
    }
    const sim = await confirmar({
        titulo: 'Apagar este evento?',
        mensagem: `"${titulo}" será apagado do site e do ERP. Isso não tem volta.`,
        rotulo: 'Apagar evento',
        perigo: true,
    });
    if (!sim) return;
    try {
        await api.del(`/api/eventos/${eventoId}`);
        toast('Evento apagado');
        location.hash = '#/eventos';
    } catch (erro) {
        toast(erro.message, 'erro');
    }
}

async function abrirNovaVan(eventoId, ctx) {
    let contatos = [];
    try {
        contatos = await api.get('/api/contatos', { somente_ativos: true });
    } catch (erro) {
        toast(erro.message, 'erro');
        return;
    }
    const motoristas = contatos.filter((c) => ['motorista', 'empresa_fretamento'].includes(c.categoria));
    janela({
        titulo: 'Nova van ou ônibus',
        botao: 'Cadastrar',
        conteudo: html`
            <div class="grade-campos">
                <div class="campo"><label for="v-nome">Nome</label>
                    <input type="text" id="v-nome" name="nome" value="Van 1" maxlength="60" required>
                    <span class="dica">Como a equipe chama: Van 1, Ônibus azul…</span></div>
                <div class="campo"><label for="v-tipo">Tipo</label>
                    <select id="v-tipo" name="tipo">${Object.entries(TIPOS_VEICULO).map(([v, t]) => html`<option value="${v}">${t}</option>`)}</select></div>
                <div class="campo"><label for="v-assentos">Quantidade de assentos</label>
                    <input type="number" id="v-assentos" name="capacidade" min="1" max="80" inputmode="numeric" value="15" required></div>
                <div class="campo"><label for="v-valor">Valor por pessoa (R$)</label>
                    <input type="text" id="v-valor" name="valor" inputmode="decimal" placeholder="0,00" autocomplete="off">
                    <span class="dica">Vale como padrão ao adicionar passageiros. Dá para mudar em cada um.</span></div>
                <div class="campo"><label for="v-placa">Placa (opcional)</label>
                    <input type="text" id="v-placa" name="placa" maxlength="10" autocomplete="off" spellcheck="false"></div>
                <div class="campo"><label for="v-contato">Motorista ou empresa (opcional)</label>
                    <select id="v-contato" name="contato_id"><option value="">Nenhum</option>
                        ${motoristas.map((c) => html`<option value="${c.id}">${c.nome}${c.empresa ? ` (${c.empresa})` : ''}</option>`)}</select>
                    <span class="dica">${motoristas.length ? 'Vem da página Contatos.' : 'Cadastre na página Contatos para escolher aqui.'}</span></div>
                <div class="campo largo"><label for="v-obs">Observações (opcional)</label>
                    <textarea id="v-obs" name="observacoes" maxlength="1000"></textarea></div>
            </div>`,
        aoEnviar: async (dados) => {
            const valor = String(dados.get('valor') || '').trim() ? lerReais(dados.get('valor')) : 0;
            if (Number.isNaN(valor)) throw erroDeTela('Informe um valor válido, como 150,00.');
            const van = await api.post('/api/veiculos', {
                evento_id: eventoId,
                nome: dados.get('nome').trim(),
                tipo: dados.get('tipo'),
                capacidade: Number(dados.get('capacidade')),
                valor_padrao_centavos: valor,
                placa: dados.get('placa').trim() || null,
                contato_id: dados.get('contato_id') ? Number(dados.get('contato_id')) : null,
                observacoes: dados.get('observacoes').trim() || null,
            });
            toast(`${van.nome} cadastrada com ${plural(van.capacidade, 'assento', 'assentos')}`);
            location.hash = `#/veiculos/${van.id}`;
        },
    });
}
