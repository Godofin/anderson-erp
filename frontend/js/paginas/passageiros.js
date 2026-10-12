import { api, ApiError } from '../api.js';
import {
    confirmar, debounce, erroDeTela, esqueleto, estadoVazio, etiquetaPagamento, html, idPassageiro, janela,
    brl, plural, toast,
} from '../ui.js';

const estado = { q: '' };

const linha = (p) => html`<tr>
    <td class="id-pessoa">${idPassageiro(p.id)}</td>
    <td><button type="button" class="link-btn" data-ver="${p.id}"><span class="nome">${p.nome}</span></button></td>
    <td class="num">${p.documento_tipo.toUpperCase()} ${p.documento_mascarado}</td>
    <td class="direita num">${p.viagens}</td>
    <td class="direita"><button type="button" class="btn btn-neutro btn-pequeno" data-ver="${p.id}">Abrir</button></td></tr>`;

const tabela = (lista) =>
    lista.length
        ? html`<div class="tabela-rolagem"><table>
            <caption class="sr-only">Passageiros cadastrados</caption>
            <thead><tr><th>ID</th><th>Nome</th><th>Documento</th><th class="direita">Viagens</th><th><span class="sr-only">Ações</span></th></tr></thead>
            <tbody>${lista.map(linha)}</tbody></table></div>`
        : estadoVazio(
              'ph-users-three',
              estado.q ? 'Ninguém encontrado' : 'Nenhum passageiro cadastrado',
              estado.q
                  ? 'Nenhum passageiro tem esse nome ou documento. Confira a digitação.'
                  : 'Cadastre quem viaja com vocês. Cada pessoa tem um ID próprio e um documento (CPF ou RG).',
          );

export async function renderizar(raiz) {
    const lista = await api.get('/api/passageiros', { q: estado.q });
    raiz.innerHTML = html`
        <div class="cabecalho">
            <div class="titulo"><h1>Passageiros</h1>
                <p>O cadastro de quem viaja. Cada pessoa é cadastrada uma vez e pode entrar em várias viagens.</p></div>
            <div class="acoes"><button class="btn btn-primario" type="button" data-acao="novo"><i class="ph ph-user-plus" aria-hidden="true"></i>Novo passageiro</button></div>
        </div>
        <div class="barra-filtros">
            <div class="busca"><i class="ph ph-magnifying-glass" aria-hidden="true"></i>
                <label class="sr-only" for="busca-pass">Buscar passageiro</label>
                <input type="search" id="busca-pass" placeholder="Buscar pelo nome ou documento…" value="${estado.q}" autocomplete="off"></div>
            <span class="muted" id="contagem" aria-live="polite">${plural(lista.length, 'passageiro', 'passageiros')}</span>
        </div>
        <div class="secao" id="lista" aria-live="polite">${tabela(lista)}</div>`.toString();
}

export function ligar(raiz, ctx) {
    const lista = raiz.querySelector('#lista');
    const contagem = raiz.querySelector('#contagem');

    async function atualizar() {
        lista.innerHTML = esqueleto(4).toString();
        try {
            const dados = await api.get('/api/passageiros', { q: estado.q });
            lista.innerHTML = tabela(dados).toString();
            contagem.textContent = plural(dados.length, 'passageiro', 'passageiros');
        } catch (erro) {
            lista.innerHTML = html`<div class="alerta erro" role="alert"><i class="ph ph-warning-circle" aria-hidden="true"></i><div>${erro.message}</div></div>`.toString();
        }
    }

    raiz.querySelector('#busca-pass').addEventListener('input', debounce((ev) => { estado.q = ev.target.value.trim(); atualizar(); }));
    raiz.addEventListener('click', (ev) => {
        const ver = ev.target.closest('[data-ver]');
        if (ver) abrirDetalhe(Number(ver.dataset.ver), atualizar);
        if (ev.target.closest('[data-acao="novo"]')) dialogNovo(ctx.recarregar);
    });
}

// ------------------------------------------------------------------ janelas
const camposDocumento = (p = {}) => html`
    <div class="campo"><label for="pd-tipo">Documento</label>
        <select id="pd-tipo" name="tipo"><option value="cpf" ${p.documento_tipo === 'cpf' ? 'selected' : ''}>CPF</option>
            <option value="rg" ${p.documento_tipo === 'rg' ? 'selected' : ''}>RG</option></select></div>
    <div class="campo"><label for="pd-numero">Número</label>
        <input type="text" id="pd-numero" name="numero" autocomplete="off" maxlength="30" value="${p.documento_formatado || ''}" required>
        <span class="dica">CPF com ou sem pontos. No RG, pode incluir letras e a sigla do estado.</span></div>`;

function dialogNovo(depois) {
    janela({
        titulo: 'Novo passageiro',
        botao: 'Cadastrar',
        conteudo: html`<div class="grade-campos">
            <div class="campo largo"><label for="pn-nome">Nome completo</label>
                <input type="text" id="pn-nome" name="nome" autocomplete="off" maxlength="120" required></div>
            ${camposDocumento()}</div>`,
        aoEnviar: async (dados) => {
            if (String(dados.get('nome')).trim().length < 3) throw erroDeTela('Informe o nome completo.');
            const p = await api.post('/api/passageiros', {
                nome: String(dados.get('nome')).trim(),
                documento_tipo: dados.get('tipo'),
                documento_numero: String(dados.get('numero')).trim(),
            });
            toast(`${p.nome} cadastrado (${idPassageiro(p.id)})`);
            depois();
        },
    });
}

/** Ficha do passageiro: documento completo, edição e histórico de viagens. */
export async function abrirDetalhe(id, aoMudar = () => {}) {
    let p;
    try {
        p = await api.get(`/api/passageiros/${id}`);
    } catch (erro) {
        toast(erro instanceof ApiError ? erro.message : 'Não foi possível abrir.', 'erro');
        return;
    }
    const ativas = p.viagens.filter((v) => v.situacao !== 'cancelado').length;
    const dlg = janela({
        titulo: `${p.nome}`,
        botao: 'Salvar alterações',
        conteudo: html`
            <p class="id-pessoa">${idPassageiro(p.id)} · ${p.documento_tipo.toUpperCase()} ${p.documento_formatado}</p>
            <div class="grade-campos">
                <div class="campo largo"><label for="pe-nome">Nome completo</label>
                    <input type="text" id="pe-nome" name="nome" value="${p.nome}" maxlength="120" required></div>
                ${camposDocumento(p)}</div>
            <div class="campo"><span class="rotulo">Viagens (${p.viagens.length})</span>
                ${p.viagens.length ? html`<ul class="historico">${p.viagens.map((v) => html`<li>
                    <span><a href="#/veiculos/${v.veiculo_id}"><strong>${v.evento_titulo || 'Viagem'}</strong></a> · ${v.veiculo_nome}</span>
                    <span>${v.situacao === 'cancelado' ? html`<span class="etiqueta neutra">Cancelada</span>`
                        : v.situacao === 'espera' ? html`<span class="etiqueta neutra"><i class="ph ph-hourglass-medium" aria-hidden="true"></i>Na espera</span>`
                        : etiquetaPagamento(v.status_pagamento)}
                        ${v.saldo_centavos > 0 && v.situacao !== 'cancelado' ? html` <span class="muted num">falta ${brl(v.saldo_centavos)}</span>` : ''}</span></li>`)}</ul>`
                    : html`<p class="muted">Ainda não está em nenhuma viagem.</p>`}</div>
            <div class="campo"><button type="button" class="btn btn-perigo btn-pequeno" data-apagar ${ativas || p.viagens.length ? 'disabled' : ''}>
                <i class="ph ph-trash" aria-hidden="true"></i>Apagar cadastro</button>
                <span class="dica">${p.viagens.length ? 'Quem já esteve em uma viagem não pode ser apagado, para manter o histórico.' : 'Só dá para apagar quem nunca esteve em uma viagem.'}</span></div>`,
        aoAbrir: (d) => {
            d.querySelector('[data-apagar]')?.addEventListener('click', async () => {
                const sim = await confirmar({ titulo: 'Apagar este cadastro?', mensagem: `${p.nome} será removido do cadastro.`, rotulo: 'Apagar', perigo: true });
                if (!sim) return;
                try {
                    await api.del(`/api/passageiros/${p.id}`);
                    d.close();
                    toast('Cadastro apagado');
                    aoMudar();
                } catch (erro) {
                    d.mostrarErro(erro.message);
                }
            });
        },
        aoEnviar: async (dados) => {
            await api.patch(`/api/passageiros/${p.id}`, {
                nome: String(dados.get('nome')).trim(),
                documento_tipo: dados.get('tipo'),
                documento_numero: String(dados.get('numero')).trim(),
            });
            toast('Cadastro atualizado');
            aoMudar();
        },
    });
    return dlg;
}
