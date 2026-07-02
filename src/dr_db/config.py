import functools 
import pathlib
import urllib.parse

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    host: str = Field(validation_alias="DR_DB_POSTGRES_HOST")
    port: int = Field(validation_alias="DR_DB_POSTGRES_PORT")
    host_port: int = Field(validation_alias="DR_DB_POSTGRES_HOST_PORT")
    db: str = Field(validation_alias="DR_DB_POSTGRES_DB")
    user: str = Field(validation_alias="DR_DB_POSTGRES_USER")
    password: SecretStr = Field(validation_alias="DR_DB_POSTGRES_PASSWORD")

    @property
    def connection_kwargs(self) -> dict[str, str | int]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.db,
            "user": self.user,
            "password": self.password.get_secret_value(),
        }

    @property
    def url(self) -> str:
        user = urllib.parse.quote(self.user, safe="")
        password = urllib.parse.quote(self.password.get_secret_value(), safe="")
        host = urllib.parse.quote(self.host, safe="")
        return f"postgresql://{user}:{password}@{host}:{self.port}/{self.db}"

    @property
    def host_url(self) -> str:
        user = urllib.parse.quote(self.user, safe="")
        password = urllib.parse.quote(self.password.get_secret_value(), safe="")
        host = urllib.parse.quote(self.host, safe="")
        return f"postgresql://{user}:{password}@{host}:{self.host_port}/{self.db}"


class DevDatabaseSettings(BaseSettings):
    host: str = Field(validation_alias="DR_DB_DEV_POSTGRES_HOST")
    port: int = Field(validation_alias="DR_DB_DEV_POSTGRES_PORT")
    host_port: int = Field(validation_alias="DR_DB_DEV_POSTGRES_HOST_PORT")
    db: str = Field(validation_alias="DR_DB_DEV_POSTGRES_DB")
    user: str = Field(validation_alias="DR_DB_DEV_POSTGRES_USER")
    password: SecretStr = Field(validation_alias="DR_DB_DEV_POSTGRES_PASSWORD")

    @property
    def connection_kwargs(self) -> dict[str, str | int]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.db,
            "user": self.user,
            "password": self.password.get_secret_value(),
        }

    @property
    def url(self) -> str:
        user = urllib.parse.quote(self.user, safe="")
        password = urllib.parse.quote(self.password.get_secret_value(), safe="")
        host = urllib.parse.quote(self.host, safe="")
        return f"postgresql://{user}:{password}@{host}:{self.port}/{self.db}"

    @property
    def host_url(self) -> str:
        user = urllib.parse.quote(self.user, safe="")
        password = urllib.parse.quote(self.password.get_secret_value(), safe="")
        host = urllib.parse.quote(self.host, safe="")
        return f"postgresql://{user}:{password}@{host}:{self.host_port}/{self.db}"


class StorageSettings(BaseSettings):
    root: pathlib.Path = Field(validation_alias="DR_DB_STORAGE_ROOT")


class MathesarSettings(BaseSettings):
    host_port: int = Field(validation_alias="MATHESAR_HOST_PORT")
    domain_name: str = Field(validation_alias="MATHESAR_DOMAIN_NAME")
    allowed_hosts: str = Field(validation_alias="MATHESAR_ALLOWED_HOSTS")
    metadata_db: str = Field(validation_alias="MATHESAR_METADATA_POSTGRES_DB")
    metadata_user: str = Field(validation_alias="MATHESAR_METADATA_POSTGRES_USER")
    metadata_password: SecretStr = Field(validation_alias="MATHESAR_METADATA_POSTGRES_PASSWORD")
    metadata_host: str = Field(validation_alias="MATHESAR_METADATA_POSTGRES_HOST")
    metadata_port: int = Field(validation_alias="MATHESAR_METADATA_POSTGRES_PORT")
    metadata_sslmode: str = Field(validation_alias="MATHESAR_METADATA_POSTGRES_SSLMODE")

    @property
    def domains(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.domain_name.split(",") if value.strip())

    @property
    def hosts(self) -> tuple[str, ...]:
        return tuple(value.strip() for value in self.allowed_hosts.split(",") if value.strip())
