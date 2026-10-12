import { api } from '../api.js';
import { linhaEvento } from '../componentes.js';
import { aplicarMedidas, debounce, esqueleto, estadoVazio, html, plural } from '../ui.js';

// Lembra o filtro ao voltar para esta página
const estado = { filtro: 'proximos', q: '' };

const FILTROS = [['proximos', 'No site'], ['fora_do_site', 'Fora do site'], ['encerrados', 'Encerradas'], ['todos', 'Todas']];

const desenharLista = (eventos) =>
    eventos.length
        ? html`<div class="lista-eventos">${eventos.map(linhaEvento)}</div>`
        : estadoVazio(
              'ph-magnifying-glass',
              'Nenhum evento encontrado',
              estado.q
                  ? 'Nenhum evento tem esse nome. Tente outra palavra.'
                  : estado.filtro === 'fora_do_site'
                      ? 'Todo evento novo nasce aqui, fora do site, até você publicar.'
                      : 'Cadastre um evento novo ou veja os que estão fora do site.',
          );

export async function renderizar(raiz) {
    const eventos = await api.get('/api/eventos', { filtro: estado.filtro, q: estado.q });
    raiz.innerHTML = html`
        <div class="cabecalho">
            <div class="titulo"><h1>Eventos e vans</h1>
                <p>Os eventos do site, com o mesmo cadastro do painel antigo. Entre em um para cadastrar as vans.</p></div>
            <div class="acoes"><a class="btn btn-primario" href="#/eventos/novo"><i class="ph ph-plus" aria-hidden="true"></i>Novo evento</a></div>
        </div>
        <div class="barra-filtros">
            <div class="segmentos" role="group" aria-label="Quais eventos mostrar">
                ${FILTROS.map(([valor, texto]) => html`<button type="button" data-filtro="${valor}" aria-pressed="${estado.filtro === valor}">${texto}</button>`)}
            </div>
            <div class="busca">
                <i class="ph ph-magnifying-glass" aria-hidden="true"></i>
                <label class="sr-only" for="busca-evento">Buscar evento</label>
                <input type="search" id="busca-evento" placeholder="Buscar por nome ou data…" value="${estado.q}" autocomplete="off">
            </div>
            <span class="muted" id="contagem" aria-live="polite">${plural(eventos.length, 'evento', 'eventos')}</span>
        </div>
        <div class="secao" id="lista" aria-live="polite">${desenharLista(eventos)}</div>`.toString();
}

export function ligar(raiz) {
    const lista = raiz.querySelector('#lista');
    const contagem = raiz.querySelector('#contagem');

    async function atualizar() {
        lista.innerHTML = esqueleto(4).toString();
        try {
            const eventos = await api.get('/api/eventos', { filtro: estado.filtro, q: estado.q });
            lista.innerHTML = desenharLista(eventos).toString();
            contagem.textContent = plural(eventos.length, 'evento', 'eventos');
            aplicarMedidas(lista);
        } catch (erro) {
            lista.innerHTML = html`<div class="alerta erro" role="alert"><i class="ph ph-warning-circle" aria-hidden="true"></i><div>${erro.message}</div></div>`.toString();
        }
    }

    raiz.querySelectorAll('[data-filtro]').forEach((botao) =>
        botao.addEventListener('click', () => {
            estado.filtro = botao.dataset.filtro;
            raiz.querySelectorAll('[data-filtro]').forEach((b) => b.setAttribute('aria-pressed', String(b === botao)));
            atualizar();
        }),
    );
    raiz.querySelector('#busca-evento').addEventListener('input', debounce((ev) => {
        estado.q = ev.target.value.trim();
        atualizar();
    }));
}
