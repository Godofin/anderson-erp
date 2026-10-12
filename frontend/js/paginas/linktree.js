/* Linktree do site: os links dos grupos de WhatsApp de cada excursão. Edita pela API do site. */

import { api } from '../api.js';
import { confirmar, dataBr, estadoVazio, html, janela, plural, toast } from '../ui.js';

const linha = (l) => html`<tr>
    <td><div class="contato-linha"><span class="nome">${l.nome}</span>
        <a class="link-linha sub" href="${l.whatsapp_url}" target="_blank" rel="noopener noreferrer">${l.whatsapp_url}</a></div></td>
    <td>${l.data_evento ? dataBr(l.data_evento) : html`<span class="muted">Sem data</span>`}</td>
    <td>${l.ativo
        ? html`<span class="etiqueta ok"><i class="ph-fill ph-check-circle" aria-hidden="true"></i>No site</span>`
        : html`<span class="etiqueta atencao"><i class="ph ph-eye-slash" aria-hidden="true"></i>Fora do site</span>`}
        ${l.destaque ? html`<span class="etiqueta neutra"><i class="ph ph-star" aria-hidden="true"></i>Destaque</span>` : ''}</td>
    <td class="direita"><button type="button" class="btn btn-neutro btn-pequeno" data-editar="${l.id}"><i class="ph ph-pencil-simple" aria-hidden="true"></i>Editar</button></td></tr>`;

export async function renderizar(raiz) {
    const links = await api.get('/api/linktree');
    raiz.innerHTML = html`
        <div class="cabecalho">
            <div class="titulo"><h1>Linktree do site</h1>
                <p>Os links dos grupos de WhatsApp. ${plural(links.length, 'link cadastrado', 'links cadastrados')}.</p></div>
            <div class="acoes"><button class="btn btn-primario" type="button" data-acao="novo"><i class="ph ph-plus" aria-hidden="true"></i>Novo link</button></div>
        </div>
        <div class="secao">${links.length
            ? html`<div class="tabela-rolagem"><table>
                <caption class="sr-only">Links do Linktree</caption>
                <thead><tr><th>Nome</th><th>Data</th><th>Situação</th><th><span class="sr-only">Ações</span></th></tr></thead>
                <tbody>${links.map(linha)}</tbody></table></div>`
            : estadoVazio('ph-link', 'Nenhum link cadastrado', 'Cadastre o link do grupo de WhatsApp de cada excursão.')}</div>`.toString();
    raiz._links = new Map(links.map((l) => [String(l.id), l]));
}

export function ligar(raiz, ctx) {
    raiz.addEventListener('click', (ev) => {
        if (ev.target.closest('[data-acao="novo"]')) return dialogLink(null, ctx.recarregar);
        const editar = ev.target.closest('[data-editar]');
        if (editar) dialogLink(raiz._links.get(editar.dataset.editar), ctx.recarregar);
    });
}

function dialogLink(l, depois) {
    const novo = !l;
    return janela({
        titulo: novo ? 'Novo link' : `Editar ${l.nome}`,
        botao: novo ? 'Cadastrar' : 'Salvar',
        conteudo: html`<div class="grade-campos">
            <div class="campo largo"><label for="l-nome">Nome</label>
                <input type="text" id="l-nome" name="nome" value="${l?.nome || ''}" maxlength="120" required
                    placeholder="Grupo Show Fulano"></div>
            <div class="campo largo"><label for="l-url">Link do grupo de WhatsApp</label>
                <input type="text" id="l-url" name="whatsapp_url" value="${l?.whatsapp_url || ''}" maxlength="1000" inputmode="url"
                    autocomplete="off" spellcheck="false" placeholder="https://chat.whatsapp.com/..." required></div>
            <div class="campo"><label for="l-data">Data do evento (opcional)</label>
                <input type="date" id="l-data" name="data_evento" value="${l?.data_evento || ''}"></div>
            <div class="campo"><label for="l-img">Imagem (opcional)</label>
                <input type="text" id="l-img" name="imagem_url" value="${l?.imagem_url || ''}" maxlength="1000" inputmode="url"
                    autocomplete="off" spellcheck="false" placeholder="https://..."></div>
            <label class="check largo"><input type="checkbox" name="ativo" ${novo || l.ativo ? 'checked' : ''}><span>Mostrar no Linktree do site</span></label>
            <label class="check largo"><input type="checkbox" name="destaque" ${l?.destaque ? 'checked' : ''}><span>Destaque</span></label>
            ${novo ? '' : html`<div class="campo largo"><button type="button" class="btn btn-perigo btn-pequeno" data-apagar>
                <i class="ph ph-trash" aria-hidden="true"></i>Apagar link</button></div>`}
        </div>`,
        aoAbrir: (d) => {
            d.querySelector('[data-apagar]')?.addEventListener('click', async () => {
                const sim = await confirmar({ titulo: 'Apagar este link?', mensagem: `${l.nome} sai do Linktree do site.`, rotulo: 'Apagar', perigo: true });
                if (!sim) return;
                try {
                    await api.del(`/api/linktree/${l.id}`);
                    d.close();
                    toast('Link apagado');
                    depois();
                } catch (erro) {
                    d.mostrarErro(erro.message);
                }
            });
        },
        aoEnviar: async (dados) => {
            const corpo = {
                nome: String(dados.get('nome')).trim(),
                whatsapp_url: String(dados.get('whatsapp_url')).trim(),
                data_evento: dados.get('data_evento') || null,
                imagem_url: String(dados.get('imagem_url')).trim() || null,
                ativo: dados.get('ativo') === 'on',
                destaque: dados.get('destaque') === 'on',
            };
            if (novo) await api.post('/api/linktree', corpo);
            else await api.put(`/api/linktree/${l.id}`, corpo);
            toast(novo ? 'Link cadastrado' : 'Link atualizado');
            depois();
        },
    });
}
