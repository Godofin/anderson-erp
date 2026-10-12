/* Chamadas à API do ERP. Mesma origem, cookie de sessão HttpOnly, só JSON. */

export class ApiError extends Error {
    constructor(status, mensagem, detalhe = null) {
        super(mensagem);
        this.status = status;
        this.detalhe = detalhe;
    }
}

const ROTULOS = {
    nome: 'O nome', email: 'O e-mail', telefone: 'O telefone', empresa: 'A empresa', categoria: 'O tipo',
    capacidade: 'A quantidade de assentos', valor_padrao_centavos: 'O valor', valor_total_centavos: 'O valor total',
    valor_centavos: 'O valor', placa: 'A placa', documento_numero: 'O documento', documento_tipo: 'O tipo de documento',
    data: 'A data', assento: 'O assento', observacoes: 'As observações', observacao: 'A observação',
    cidade_embarque: 'A cidade de embarque', senha: 'A senha', tipo: 'O tipo',
    titulo: 'O título', imagem: 'A imagem', descricao: 'A descrição', data_texto: 'A data em texto',
    data_evento: 'A data do evento', texto_botao: 'O texto do botão', link_botao: 'O link do botão',
    saiba_mais_link: 'O link do saiba mais', whatsapp_url: 'O link do grupo', imagem_url: 'A imagem',
};

/** Traduz um erro de validação do servidor (em inglês) para uma frase em português. */
function traduzirValidacao(erro) {
    const campo = Array.isArray(erro.loc) ? String(erro.loc[erro.loc.length - 1]) : '';
    const rotulo = ROTULOS[campo] || 'Um dos campos';
    const msg = String(erro.msg || '');
    switch (erro.type) {
        case 'missing': return `Falta preencher: ${rotulo.replace(/^(O|A)s? /, '').toLowerCase()}.`;
        case 'string_too_short': return `${rotulo} está curto demais.`;
        case 'string_too_long': return `${rotulo} está longo demais.`;
        case 'greater_than_equal': case 'greater_than': return `${rotulo} está abaixo do mínimo permitido.`;
        case 'less_than_equal': case 'less_than': return `${rotulo} passou do máximo permitido.`;
        case 'int_parsing': case 'int_type': case 'float_parsing': return `${rotulo} precisa ser um número.`;
        case 'literal_error': case 'enum': return `${rotulo} tem uma opção inválida.`;
        case 'date_from_datetime_parsing': case 'date_parsing': case 'date_type': return `${rotulo} não é uma data válida.`;
        default:
            if (/email/i.test(msg)) return 'Informe um e-mail válido, como nome@empresa.com.br.';
            // mensagens escritas por nós já vêm em português ("CPF inválido...")
            return msg.replace(/^Value error,\s*/i, '') || 'Confira os dados informados.';
    }
}

/** Transforma o "detail" da API (texto, objeto ou lista de erros de validação) numa frase para a tela. */
function mensagemDe(detail, status) {
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && !Array.isArray(detail) && detail.mensagem) return detail.mensagem;
    if (Array.isArray(detail) && detail.length) return traduzirValidacao(detail[0]);
    if (status >= 500) return 'Algo deu errado do nosso lado. Tente de novo em instantes.';
    return 'Não foi possível concluir. Tente de novo.';
}

async function chamar(metodo, url, corpo) {
    let resposta;
    try {
        resposta = await fetch(url, {
            method: metodo,
            headers: corpo === undefined ? {} : { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: corpo === undefined ? undefined : JSON.stringify(corpo),
        });
    } catch (erro) {
        throw new ApiError(0, 'Sem conexão com o servidor. Verifique a internet e tente de novo.');
    }
    if (resposta.status === 204) return null;
    let dados = null;
    try {
        dados = await resposta.json();
    } catch (erro) {
        dados = null;
    }
    if (!resposta.ok) {
        if (resposta.status === 401 && !url.startsWith('/api/auth/')) {
            window.dispatchEvent(new CustomEvent('sessao-expirada'));
        }
        const detail = dados && dados.detail;
        throw new ApiError(resposta.status, mensagemDe(detail, resposta.status), detail);
    }
    return dados;
}

export const api = {
    get: (url, params) => {
        const consulta = params
            ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')).toString()
            : '';
        return chamar('GET', url + (consulta === '?' ? '' : consulta));
    },
    post: (url, corpo = {}) => chamar('POST', url, corpo),
    put: (url, corpo) => chamar('PUT', url, corpo),
    patch: (url, corpo) => chamar('PATCH', url, corpo),
    del: (url) => chamar('DELETE', url),
};
