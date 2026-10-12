/* Cadastro e edição de evento do site. Mesmos campos do painel admin antigo, gravados pela API do site. */

import { api } from '../api.js';
import { html, toast } from '../ui.js';

const MESES = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'];

/** "2026-12-10" -> "10 de dezembro de 2026" (sugestão para o texto da data). */
function dataPorExtenso(iso) {
    const [a, m, d] = String(iso || '').split('-').map(Number);
    return a && m && d ? `${d} de ${MESES[m - 1]} de ${a}` : '';
}

const VAZIO = {
    titulo: '', tipo: 'show', imagem: '', descricao: '', data_texto: '', data_evento: '',
    texto_botao: 'Reservar agora', destino_botao: 'whatsapp', link_botao: '', cidades: [],
    saiba_mais_link: '', ativo: false, destaque: false,
};

export async function renderizar(raiz, ctx) {
    const [id] = ctx.ids;
    const ficha = id ? await api.get(`/api/eventos/${id}/ficha`) : null;
    const e = { ...VAZIO, ...(ficha || {}) };
    ctx.titulo(ficha ? `Editar ${e.titulo}` : 'Novo evento');
    raiz.dataset.evento = id || '';
    raiz.dataset.linkWhatsapp = ficha?.link_whatsapp || '';
    raiz.innerHTML = html`
        <a class="voltar" href="${ficha ? `#/eventos/${id}` : '#/eventos'}"><i class="ph ph-arrow-left" aria-hidden="true"></i>${ficha ? 'Voltar ao evento' : 'Eventos e vans'}</a>
        <div class="cabecalho">
            <div class="titulo"><h1>${ficha ? 'Editar evento' : 'Novo evento'}</h1>
                <p>${ficha
                    ? 'As mudanças vão para o site assim que você salvar.'
                    : 'O evento nasce fora do site. Você escolhe a hora de publicar.'}</p></div>
        </div>

        <form id="form-evento" class="form-evento" novalidate>
            <section class="painel"><div class="painel-corpo grade-campos">
                <div class="campo largo"><label for="f-titulo">Título</label>
                    <input type="text" id="f-titulo" name="titulo" value="${e.titulo}" maxlength="200" required
                        placeholder="Excursão BTS - São Paulo">
                    <span class="dica">É o nome que aparece no site e no ERP.</span></div>
                <div class="campo"><label for="f-tipo">Tipo</label>
                    <select id="f-tipo" name="tipo">
                        <option value="show" ${e.tipo === 'show' ? 'selected' : ''}>Show ou evento</option>
                        <option value="eco" ${e.tipo === 'eco' ? 'selected' : ''}>Ecoturismo ou viagem</option></select></div>
                <div class="campo"><label for="f-data">Data do evento</label>
                    <input type="date" id="f-data" name="data_evento" value="${e.data_evento || ''}" required>
                    <span class="dica">Se for mais de um dia, use o último dia.</span></div>
                <div class="campo largo"><label for="f-data-texto">Data como aparece no site</label>
                    <input type="text" id="f-data-texto" name="data_texto" value="${e.data_texto}" maxlength="200" required
                        placeholder="10 de dezembro de 2026 - São Paulo">
                    <span class="dica">Texto livre. Preenche sozinho pela data, e você pode ajustar (cidade do show, vários dias).</span></div>
                <div class="campo largo"><label for="f-descricao">Descrição</label>
                    <textarea id="f-descricao" name="descricao" maxlength="6000" required>${e.descricao}</textarea></div>
                <div class="campo largo"><label for="f-cidades">Cidades de saída</label>
                    <input type="text" id="f-cidades" name="cidades" value="${e.cidades.join(', ')}" maxlength="400"
                        placeholder="Araraquara, São Carlos">
                    <span class="dica">Separe por vírgula.</span></div>
            </div></section>

            <section class="painel"><div class="painel-corpo grade-campos">
                <div class="campo largo"><label for="f-imagem">Imagem (endereço)</label>
                    <input type="text" id="f-imagem" name="imagem" value="${e.imagem}" maxlength="1000" inputmode="url"
                        autocomplete="off" spellcheck="false" placeholder="https://...">
                    <span class="dica">O endereço completo da imagem do cartaz.</span></div>
                <div class="previa largo"><div class="previa-caixa">
                    <img id="previa-img" alt="Pré-visualização da imagem do evento" width="160" height="200" hidden>
                    <span class="muted" id="previa-vazia"><i class="ph ph-image" aria-hidden="true"></i>Sem imagem</span></div></div>
            </div></section>

            <section class="painel"><div class="painel-corpo grade-campos">
                <div class="campo"><label for="f-botao">Texto do botão</label>
                    <input type="text" id="f-botao" name="texto_botao" value="${e.texto_botao}" maxlength="60" required></div>
                <fieldset class="campo"><legend>Para onde o botão leva</legend>
                    <label class="check"><input type="radio" name="destino_botao" value="whatsapp" ${e.destino_botao === 'whatsapp' ? 'checked' : ''}>
                        <span>WhatsApp da empresa, com mensagem pronta sobre o evento</span></label>
                    <label class="check"><input type="radio" name="destino_botao" value="link" ${e.destino_botao === 'link' ? 'checked' : ''}>
                        <span>Outro link (loja, formulário...)</span></label></fieldset>
                <div class="campo largo" id="bloco-link" ${e.destino_botao === 'link' ? '' : 'hidden'}>
                    <label for="f-link">Link do botão</label>
                    <input type="text" id="f-link" name="link_botao" value="${e.link_botao || ''}" maxlength="1000" inputmode="url"
                        autocomplete="off" spellcheck="false" placeholder="https://..."></div>
                <p class="dica largo" id="bloco-whats" ${e.destino_botao === 'link' ? 'hidden' : ''}>
                    ${ficha ? html`<a href="${ficha.link_whatsapp}" target="_blank" rel="noopener noreferrer">Testar o link do WhatsApp deste evento</a>` : 'O link do WhatsApp é montado sozinho a partir do título.'}</p>
                <div class="campo largo"><label for="f-saiba">Página do "Saiba mais" (opcional)</label>
                    <input type="text" id="f-saiba" name="saiba_mais_link" value="${e.saiba_mais_link || ''}" maxlength="1000"
                        autocomplete="off" spellcheck="false" placeholder="bts.html">
                    <span class="dica">O nome de uma página do site (bts.html) ou um endereço completo.</span></div>
            </div></section>

            <section class="painel"><div class="painel-corpo grade-campos">
                <label class="check largo"><input type="checkbox" name="ativo" ${e.ativo ? 'checked' : ''}>
                    <span><strong>Mostrar no site</strong><br><span class="muted">Desligado, o evento fica só aqui no ERP. Ligado, aparece para todo mundo no site.</span></span></label>
                <label class="check largo"><input type="checkbox" name="destaque" ${e.destaque ? 'checked' : ''}>
                    <span><strong>Evento em destaque</strong><br><span class="muted">Ganha destaque na página inicial.</span></span></label>
            </div></section>

            <p class="erro" id="erro-form" role="alert" hidden></p>
            <div class="rodape-form">
                <a class="btn btn-neutro" href="${ficha ? `#/eventos/${id}` : '#/eventos'}">Cancelar</a>
                <button class="btn btn-primario" type="submit" id="salvar"><i class="ph ph-floppy-disk" aria-hidden="true"></i>${ficha ? 'Salvar mudanças' : 'Cadastrar evento'}</button>
            </div>
        </form>`.toString();
}

export function ligar(raiz) {
    const form = raiz.querySelector('#form-evento');
    const erro = raiz.querySelector('#erro-form');
    const id = raiz.dataset.evento;
    const dataTexto = form.elements.data_texto;
    const imagem = form.elements.imagem;
    const previaImg = raiz.querySelector('#previa-img');
    const previaVazia = raiz.querySelector('#previa-vazia');

    // Texto da data: sugere pela data escolhida, sem sobrescrever o que a pessoa escreveu
    let mexeuNoTexto = Boolean(dataTexto.value.trim());
    dataTexto.addEventListener('input', () => { mexeuNoTexto = true; });
    form.elements.data_evento.addEventListener('change', (ev) => {
        if (!mexeuNoTexto) dataTexto.value = dataPorExtenso(ev.target.value);
    });

    // Pré-visualização da imagem
    // O espaço da prévia fica sempre reservado: se ela aparecesse só depois, empurraria o botão Salvar
    const mostrarPrevia = () => {
        const url = imagem.value.trim();
        const valida = /^https?:\/\//i.test(url);
        if (valida) previaImg.src = url; else previaImg.removeAttribute('src');
        previaImg.hidden = !valida;
        previaVazia.hidden = valida;
    };
    previaImg.addEventListener('error', () => { previaImg.hidden = true; previaVazia.hidden = false; });
    imagem.addEventListener('change', mostrarPrevia);
    if (imagem.value.trim()) mostrarPrevia();

    // Destino do botão
    form.querySelectorAll('[name="destino_botao"]').forEach((r) => r.addEventListener('change', () => {
        const link = form.elements.destino_botao.value === 'link';
        raiz.querySelector('#bloco-link').hidden = !link;
        raiz.querySelector('#bloco-whats').hidden = link;
    }));

    form.addEventListener('submit', async (ev) => {
        ev.preventDefault();
        const botao = raiz.querySelector('#salvar');
        const f = form.elements;
        const corpo = {
            titulo: f.titulo.value.trim(),
            tipo: f.tipo.value,
            imagem: f.imagem.value.trim(),
            descricao: f.descricao.value.trim(),
            data_texto: f.data_texto.value.trim(),
            data_evento: f.data_evento.value,
            texto_botao: f.texto_botao.value.trim(),
            destino_botao: f.destino_botao.value,
            link_botao: f.link_botao.value.trim() || null,
            cidades: f.cidades.value.split(',').map((c) => c.trim()).filter(Boolean),
            saiba_mais_link: f.saiba_mais_link.value.trim() || null,
            ativo: f.ativo.checked,
            destaque: f.destaque.checked,
        };
        const faltando = [['titulo', 'o título'], ['data_evento', 'a data do evento'], ['data_texto', 'a data como aparece no site'],
            ['descricao', 'a descrição'], ['imagem', 'o endereço da imagem']].find(([chave]) => !corpo[chave]);
        if (faltando) {
            erro.textContent = `Falta preencher ${faltando[1]}.`;
            erro.hidden = false;
            f[faltando[0]].focus();
            return;
        }
        erro.hidden = true;
        botao.disabled = true;
        try {
            const salvo = id ? await api.put(`/api/eventos/${id}`, corpo) : await api.post('/api/eventos', corpo);
            toast(id ? 'Evento atualizado no site' : 'Evento cadastrado');
            location.hash = `#/eventos/${salvo.id}`;
        } catch (e) {
            erro.textContent = e.message || 'Não foi possível salvar.';
            erro.hidden = false;
            erro.scrollIntoView({ block: 'center', behavior: 'smooth' });
            botao.disabled = false;
        }
    });
}
