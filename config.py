from datetime import timedelta
from enum import Enum
from functools import lru_cache
from typing import Dict

import yaml

from pydantic import (
    BaseSettings,
    NameEmail,
    SecretStr,
)


class Modalidad(str, Enum):
    GRUPAL = "g"
    INDIVIDUAL = "i"
    PARCIALITO = "p"


class Settings(BaseSettings):
    test: bool
    title: str
    sender: NameEmail

    spreadsheet_id: str
    planilla_ttl: timedelta

    cuatri: str
    entregas: Dict[str, Modalidad]
    disabled_entregas: Dict[str, Modalidad]

    oauth_client_id: str
    oauth_client_secret: SecretStr
    oauth_refresh_token: SecretStr
    service_account_jsonfile: str

    recaptcha_site_id: str
    recaptcha_secret: SecretStr


@lru_cache
def load_config():
    """Carga la configuración de un archivo YAML.

    Returns:
       un objeto de tipo Settings, validado.
    """
    # FIXME: estaría mejor si las variables de entorno pudieran tomar
    # precedencia sobre la configuración en YAML (ver el orden de prioridad en
    # https://pydantic-docs.helpmanual.io/usage/settings/#field-value-priority).
    with open("entregas.yml") as yml:
        return Settings(**yaml.safe_load(yml), _env_file=".secrets")
