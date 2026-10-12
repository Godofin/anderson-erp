from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CHAVE_DE_EXEMPLO = "chave-de-desenvolvimento-nao-use-em-producao"
PASTA_DO_PROJETO = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PASTA_DO_PROJETO / ".env", env_prefix="ERP_", extra="ignore")

    ambiente: Literal["dev", "prod"] = "dev"
    database_url: str = Field(
        default=f"sqlite:///{(PASTA_DO_PROJETO / 'erp.db').as_posix()}",
        validation_alias=AliasChoices("ERP_DATABASE_URL", "DATABASE_URL"),
    )
    secret_key: str = CHAVE_DE_EXEMPLO
    sessao_horas: int = Field(default=12, ge=1, le=72)
    api_publica: str = "https://fast-api-anderson.vercel.app/api/v1"
    eventos_cache_segundos: int = Field(default=60, ge=0)
    # número que recebe as mensagens dos botões "Reservar" do site (só dígitos, com DDI)
    whatsapp_numero: str = "5516988332631"

    def validar_para_producao(self) -> None:
        """Recusa subir em produção com a chave de exemplo ou uma chave curta."""
        if self.ambiente != "prod":
            return
        if self.secret_key == CHAVE_DE_EXEMPLO or len(self.secret_key) < 32:
            raise RuntimeError(
                "ERP_SECRET_KEY precisa ter pelo menos 32 caracteres em produção "
                "(não use a chave de exemplo)."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
