import { api } from '../api.js';
import {
    CATEGORIAS, confirmar, debounce, esqueleto, estadoVazio, html, janela, linkWhatsApp, plural, toast,
} from '../ui.js';

const estado = { q: '', categoria: '', inativos: false };

const ICONE = {
    motorista: 'ph-steering-wheel',
    empresa_fretamento: 'ph-buildings',
    guia: 'ph-flag-banner',
    fornecedor: 'ph-package',
    outro: 'ph-address-book',
};

const linha = (c) => html`<tr>
    <td><div class="contato-linha"><span class="nome">${c.nome}</span>${c.empresa ? html`<span class="sub">${c.empresa}</span>` : ''}</div></td>
    <td><span class="etiqueta neutra"><i class="ph ${ICONE[c.categoria]}" aria-hidden="true"></i>${CATEGORIAS[c.categoria]}</span></td>
    <td>${c.telefone
        ? html`<div class="acoes-linha">${linkWhatsApp(c.telefone)
            ? html`<a class="link-linha" href="${linkWhatsApp(c.telefone)}" target="_blank" rel="noopener noreferrer" aria-label="Chamar ${c.nome} no WhatsApp">${c.telefone}</a>`
            : c.telefone}</div>`
        : html`<span class="muted">Sem telefone</span>`}</td>
    <td>${c.email ? html`<a class="link-linha" href="mailto:${c.email}">${c.email}</a>` : html`<span class="muted">Sem e-mail</span>`}</td>
    <td class="direita num">${c.veiculos}</td>
    <td>${c.ativo ? html`<span class="etiqueta ok"><i class="ph-fill ph-check-circle" aria-hidden="true"></i>Ativo</span>` : html`<span class="etiqueta neutra">Inativo</span>`}</td>
    <td class="direita"><button type="button" class="btn btn-neutro btn-pequeno" data-editar="${c.id}"><i class="ph ph-pencil-simple" aria-hidden="true"></i>Editar</button></td></tr>`;

const tabela = (lista) =>
    lista.length
        ? html`<div class="tabela-rolagem"><table>
            <caption class="sr-only">Contatos de apoio</caption>
            <thead><tr><th>Nome</th><th>Tipo</th><th>Telefone</th><th>E-mail</th><th class="direita">Vans</th><th>Situação</th><th><span class="sr-only">Ações</span></th></tr></thead>
            <tbody>${lista.map(linha)}</tbody></table></div>`
        : estadoVazio(
              'ph-address-book',
              'Nenhum contato encontrado',
              estado.q || estado.categoria
                  ? 'Nenhum contato combina com esse filtro.'
                  : 'Cadastre motoristas, empresas de fretamento, guias e fornecedores. Depois é só ligar cada um à sua van.',
          );

const consulta = () => ({ q: estado.q, categoria: estado.categoria, somente_ativos: estado.inativos ? '' : true });

export async function renderizar(raiz) {
    const lista = await api.get('/api/contatos', consulta());
    raiz.innerHTML = html`
        <div class="cabecalho">
            <div class="titulo"><h1>Contatos</h1><p>Motoristas, empresas de fretamento, guias e outros contatos de apoio às viagens.</p></div>
            <div class="acoes"><button class="btn btn-primario" type="button" data-acao="novo"><i class="ph ph-plus" aria-hidden="true"></i>Novo contato</button></div>
        </div>
        <div class="barra-filtros">
            <div class="busca"><i class="ph ph-magnifying-glass" aria-hidden="true"></i>
                <label class="sr-only" for="busca-contato">Buscar contato</label>
                <input type="search" id="busca-contato" placeholder="Buscar por nome, empresa ou telefone…" value="${estado.q}" autocomplete="off"></div>
            <div class="chips" role="group" aria-label="Filtrar por tipo">
                <button type="button" class="filtro" data-cat="" aria-pressed="${estado.categoria === ''}">Todos</button>
                ${Object.entries(CATEGORIAS).map(([k, t]) => html`<button type="button" class="filtro" data-cat="${k}" aria-pressed="${estado.categoria === k}">${t}</button>`)}
            </div>
            <label class="check"><input type="checkbox" id="ver-inativos" ${estado.inativos ? 'checked' : ''}><span>Mostrar inativos</span></label>
            <span class="muted" id="contagem" aria-live="polite">${plural(lista.length, 'contato', 'contatos')}</span>
        </div>
        <div class="secao" id="lista" aria-live="polite">${tabela(lista)}</div>`.toString();
    raiz._contatos = new Map(lista.map((c) => [String(c.id), c]));
}

export function ligar(raiz, ctx) {
    const lista = raiz.querySelector('#lista');
    const contagem = raiz.querySelector('#contagem');

    async function atualizar() {
        lista.innerHTML = esqueleto(4).toString();
        try {
            const dados = await api.get('/api/contatos', consulta());
            raiz._contatos = new Map(dados.map((c) => [String(c.id), c]));
            lista.innerHTML = tabela(dados).toString();
            contagem.textContent = plural(dados.length, 'contato', 'contatos');
        } catch (erro) {
            lista.innerHTML = html`<div class="alerta erro" role="alert"><i class="ph ph-warning-circle" aria-hidden="true"></i><div>${erro.message}</div></div>`.toString();
        }
    }

    raiz.querySelector('#busca-contato').addEventListener('input', debounce((ev) => { estado.q = ev.target.value.trim(); atualizar(); }));
    raiz.querySelector('#ver-inativos').addEventListener('change', (ev) => { estado.inativos = ev.target.checked; atualizar(); });
    raiz.querySelectorAll('[data-cat]').forEach((b) => b.addEventListener('click', () => {
        estado.categoria = b.dataset.cat;
        raiz.querySelectorAll('[data-cat]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
        atualizar();
    }));
    raiz.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-acao="novo"]')) return dialogContato(null, ctx.recarregar);
        const editar = ev.target.closest('[data-editar]');
        if (editar) dialogContato(raiz._contatos.get(editar.dataset.editar), ctx.recarregar);
    });
}

function dialogContato(c, depois) {
    const novo = !c;
    const dlg = janela({
        titulo: novo ? 'Novo contato' : `Editar ${c.nome}`,
        botao: novo ? 'Cadastrar' : 'Salvar',
        conteudo: html`<div class="grade-campos">
            <div class="campo"><label for="c-nome">Nome</label><input type="text" id="c-nome" name="nome" value="${c?.nome || ''}" maxlength="120" required></div>
            <div class="campo"><label for="c-cat">Tipo</label>
                <select id="c-cat" name="categoria">${Object.entries(CATEGORIAS).map(([k, t]) => html`<option value="${k}" ${(c?.categoria || 'motorista') === k ? 'selected' : ''}>${t}</option>`)}</select></div>
            <div class="campo"><label for="c-empresa">Empresa (opcional)</label><input type="text" id="c-empresa" name="empresa" value="${c?.empresa || ''}" maxlength="120"></div>
            <div class="campo"><label for="c-tel">Telefone ou WhatsApp</label>
                <input type="tel" id="c-tel" name="telefone" value="${c?.telefone || ''}" maxlength="30" inputmode="tel" placeholder="(16) 99999-0000" autocomplete="off"></div>
            <div class="campo largo"><label for="c-email">E-mail (opcional)</label>
                <input type="email" id="c-email" name="email" value="${c?.email || ''}" maxlength="200" autocomplete="off" spellcheck="false"></div>
            <div class="campo largo"><label for="c-obs">Observações (opcional)</label><textarea id="c-obs" name="observacoes" maxlength="1000">${c?.observacoes || ''}</textarea></div>
            <label class="check largo"><input type="checkbox" name="ativo" ${novo || c.ativo ? 'checked' : ''}><span>Contato ativo (aparece na escolha de motorista ou empresa das vans)</span></label>
            ${novo ? '' : html`<div class="campo largo"><button type="button" class="btn btn-perigo btn-pequeno" data-apagar>
                <i class="ph ph-trash" aria-hidden="true"></i>Apagar contato</button>
                <span class="dica">${c.veiculos ? `Está ligado a ${plural(c.veiculos, 'van', 'vans')}. Desative em vez de apagar.` : 'Dá para apagar porque não está ligado a nenhuma van.'}</span></div>`}
        </div>`,
        aoAbrir: (d) => {
            d.querySelector('[data-apagar]')?.addEventListener('click', async () => {
                if (c.veiculos) { d.mostrarErro(`Este contato está ligado a ${plural(c.veiculos, 'van', 'vans')}. Desative em vez de apagar.`); return; }
                const sim = await confirmar({ titulo: 'Apagar este contato?', mensagem: `${c.nome} será removido.`, rotulo: 'Apagar', perigo: true });
                if (!sim) return;
                try {
                    await api.del(`/api/contatos/${c.id}`);
                    d.close();
                    toast('Contato apagado');
                    depois();
                } catch (erro) {
                    d.mostrarErro(erro.message);
                }
            });
        },
        aoEnviar: async (dados) => {
            const corpo = {
                nome: String(dados.get('nome')).trim(),
                categoria: dados.get('categoria'),
                empresa: String(dados.get('empresa')).trim() || null,
                telefone: String(dados.get('telefone')).trim() || null,
                email: String(dados.get('email')).trim() || null,
                observacoes: String(dados.get('observacoes')).trim() || null,
                ativo: dados.get('ativo') === 'on',
            };
            if (novo) await api.post('/api/contatos', corpo);
            else await api.patch(`/api/contatos/${c.id}`, corpo);
            toast(novo ? 'Contato cadastrado' : 'Contato atualizado');
            depois();
        },
    });
    return dlg;
}
