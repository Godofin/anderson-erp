"""Validação, normalização e máscara de CPF e RG."""

import re

SEM_FORMATO = re.compile(r"[^0-9A-Za-z]")


def normalizar_cpf(texto: str) -> str:
    return re.sub(r"\D", "", texto)


def cpf_valido(cpf: str) -> bool:
    """CPF com 11 dígitos, sem sequência repetida e com os dois dígitos verificadores corretos."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def normalizar_rg(texto: str) -> str:
    """RG varia por estado e pode ter letras (ex.: dígito X). Guarda só letras e números."""
    return SEM_FORMATO.sub("", texto).upper()


def normalizar_documento(tipo: str, texto: str) -> str:
    """Devolve o documento normalizado ou levanta ValueError com a mensagem para o usuário."""
    if tipo == "cpf":
        cpf = normalizar_cpf(texto)
        if not cpf_valido(cpf):
            raise ValueError("CPF inválido. Confira os 11 dígitos.")
        return cpf
    rg = normalizar_rg(texto)
    if not 5 <= len(rg) <= 14:
        raise ValueError("RG inválido. Informe de 5 a 14 letras ou números.")
    return rg


def formatar_documento(tipo: str, numero: str) -> str:
    if tipo == "cpf" and len(numero) == 11:
        return f"{numero[:3]}.{numero[3:6]}.{numero[6:9]}-{numero[9:]}"
    return numero


def mascarar_documento(tipo: str, numero: str) -> str:
    """Mostra só os 3 dígitos do meio do CPF (ou os 3 últimos do RG). Basta para conferir."""
    if tipo == "cpf" and len(numero) == 11:
        return f"***.***.{numero[6:9]}-**"
    return "•" * max(len(numero) - 3, 0) + numero[-3:]
