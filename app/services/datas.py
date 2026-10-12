"""Leitura das datas dos eventos da API pública.

A API guarda a data como texto livre ("25 e 27 de outubro - São Paulo") e o campo date_event
nem sempre bate com o dia do show. Por isso o texto vale primeiro e date_event serve de apoio.
"""

import re
from datetime import date

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]  # fmt: skip

PADRAO = re.compile(
    r"(\d{1,2}(?:\s*(?:,|e|a|-|–)\s*\d{1,2})*)\s+de\s+"
    r"(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
    r"(?:\s+(?:de\s+)?(\d{4}))?",
    re.IGNORECASE,
)


def ler_datas(texto: str | None, data_evento: str | None, ano: str | None) -> tuple[date | None, date | None]:
    """Devolve (primeiro dia, último dia) do evento, ou (None, None) se não der para saber."""
    ano_padrao = int(ano) if ano and ano.isdigit() else None
    if data_evento and not ano_padrao:
        try:
            ano_padrao = int(data_evento[:4])
        except ValueError:
            ano_padrao = None

    achado = PADRAO.search(texto or "")
    if achado:
        ano_evento = int(achado.group(3)) if achado.group(3) else ano_padrao
        if ano_evento is not None:
            dias = [int(d) for d in re.findall(r"\d{1,2}", achado.group(1))]
            mes = MESES.index(achado.group(2).lower().replace("marco", "março")) + 1
            try:
                return date(ano_evento, mes, dias[0]), date(ano_evento, mes, dias[-1])
            except ValueError:
                pass

    if data_evento:
        try:
            dia = date.fromisoformat(data_evento[:10])
            return dia, dia
        except ValueError:
            pass
    return None, None
