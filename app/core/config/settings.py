"""
Application configuration using Pydantic Settings.
"""

import os
import sys
from abc import ABC
from functools import lru_cache, reduce
from sqlalchemy.engine.url import URL
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import ErrorDetails
from pydantic import Field, ValidationError
from typing import TypeVar

BASE_DIR = os.getcwd()

T = TypeVar('T', bound=BaseSettings)


class Settings(BaseSettings, ABC):
    """Base settings class with support for .env and .env.local files.

    .env.local will override variables from .env, similar to
    docker-compose.override.yml behavior.
    """

    model_config = SettingsConfigDict(
        env_file=[
            os.path.join(BASE_DIR, '.env'),
            os.path.join(BASE_DIR, '.env.local')
        ],
        env_file_encoding="utf-8",
        extra='ignore'
    )


class GeneralSettings(Settings):
    """Application settings"""

    # API settings
    PORT: int = Field(default=4000, description="API port")
    DEBUG: bool = Field(default=False, description="Debug mode")


class DatabaseSettings(Settings):
    """Database settings"""

    DB_HOST: str = Field(..., description="Database host")
    DB_PORT: int = Field(..., description="Database port")
    DB_NAME: str = Field(..., description="Database name")
    DB_USER: str = Field(..., description="Database user")
    DB_PASSWORD: str = Field(..., description="Database password")

    SSL_MODE: bool = Field(default=False, description="SSL mode")

    @property
    def database_url_obj(self) -> URL:
        """Generate database URL object for sync connections"""

        # Add SSL query parameters
        # (psycopg2 uses 'sslmode', not 'ssl')
        query = {}
        if self.SSL_MODE:
            query = {"sslmode": "require"}

        obj: URL = URL.create(
            drivername="postgresql+psycopg2",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query=query,
        )

        return obj

    @property
    def database_url_obj_async(self) -> URL:
        """Generate database URL object for async connections"""

        # Add SSL query parameters
        # (asyncpg uses 'ssl', not 'sslmode')
        query = {}
        if self.SSL_MODE:
            query = {"ssl": "require"}

        obj: URL = URL.create(
            drivername="postgresql+asyncpg",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query=query,
        )

        return obj


class RedisSettings(Settings):
    """Redis settings"""
    redis_host: str = Field(
        ..., description="Redis host",
        alias="REDIS_HOST"
    )
    redis_port: int = Field(
        ..., description="Redis port",
        alias="REDIS_PORT"
    )
    redis_password: str = Field(
        ..., description="Redis password",
        alias="REDIS_PASSWORD"
    )
    redis_ssl: bool = Field(
        ..., description="Redis SSL",
        alias="REDIS_SSL"
    )

    @property
    def redis_url(self) -> str:
        """Generate Redis URL"""
        # Use rediss:// for SSL connections, redis:// for non-SSL
        scheme = "rediss" if self.redis_ssl else "redis"

        # Format: redis://[password@]host:port[/database]
        if self.redis_password:
            auth_part = f"{self.redis_password}@"
        else:
            auth_part = ""

        return f"{scheme}://{auth_part}{self.redis_host}:{self.redis_port}"


class InstructorSettings(Settings):
    """Instructor settings"""

    api_key: str = Field(
        ...,
        alias="OPENAI_API_KEY",
        description="OpenAI API key"
    )


def _format_validation_errors(errors: list[ErrorDetails]) -> str:
    """Format validation errors into a readable string"""

    def format_error(acc: list[list[str]], error: ErrorDetails) -> \
            list[list[str]]:
        error_type = error.get('type', 'unknown').capitalize()
        error_loc = f"{', '.join(map(str, error.get('loc', [])))}"

        # Find if error type already exists
        for item in acc:
            if item[0] == error_type:
                item[1] += f", {error_loc}"
                return acc

        # If not found, append new error type
        acc.append([error_type, error_loc])
        return acc

    return ", ".join(
        f"{error_type}: {error_msg}"
        for error_type, error_msg
        in reduce(format_error, errors, list[list[str]]([]))
    )


def _get_settings(settings_class: type[T]) -> T:
    """Generic function to get cached settings instance"""
    try:
        return settings_class()
    except ValidationError as e:
        print(
            "Error: There are some errors in the .env file.\n"
            f"{_format_validation_errors(e.errors())}\n"
            "Please check your .env file."
        )
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {type(e).__name__}")
        print(e)
        sys.exit(1)


@lru_cache()
def get_settings() -> GeneralSettings:
    """Get cached Settings instance"""
    return _get_settings(GeneralSettings)


@lru_cache()
def get_database_settings() -> DatabaseSettings:
    """Get cached Database settings instance"""
    return _get_settings(DatabaseSettings)


@lru_cache()
def get_redis_settings() -> RedisSettings:
    """Get cached Redis settings instance"""
    return _get_settings(RedisSettings)


@lru_cache()
def get_instructor_settings() -> InstructorSettings:
    """Get cached Instructor settings instance"""
    return _get_settings(InstructorSettings)
