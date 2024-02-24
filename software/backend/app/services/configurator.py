"""
Configurator service. This service is responsible for configuring the
application. It uses a simple JSON file to store the configuration. The
configuration file is loaded when the application starts and saved whenever
the configuration changes. The configuration file is located in the backend
directory and is called `config.json`.
"""

import asyncio
import json
import logging
import os
from dataclasses import asdict, fields
from typing import Callable

from .. import data_dir
from ..models.config import Config

LOGGER = logging.getLogger(__name__)
"""Configurator logger."""

config: Config
"""The configuration settings."""
config_file = os.path.join(data_dir, "config.json")
"""The configuration file path."""
validators: dict[str, list[Callable[..., None]]] = {}
"""The configuration validators. Called when a setting is changed."""

_config_lock = asyncio.Lock()  # lock for accessing the configuration


async def set_config(new_config: Config) -> dict:
    """Update the active configuration.

    Args:
        new_config (Config): The new configuration.

    Returns:
        Config: The new configuration.
    """
    global config

    # validate new config
    for field in fields(new_config):
        new_value = getattr(new_config, field.name)
        if field.name in validators:
            for validator in validators[field.name]:
                try:
                    validator(new_value)
                except Exception as e:
                    raise ValidationError(
                        f"Invalid value for {field.name}: {new_value}"
                    ) from e

    # lock to update and store new config
    async with _config_lock:
        config = new_config
        return asdict(_store_config(config))


async def get_config() -> dict:
    """Get the active configuration.

    Returns:
        Config: The active configuration.
    """
    global config

    # wait for the lock (therefore config) to be available
    async with _config_lock:
        return asdict(config)


def register_validator(key: str, validator: Callable[..., None]):
    """Register a configuration validator.

    Args:
        key (str): The configuration key.
        validator (Callable[..., bool]): The validator function.

    Returns:
        Callable[..., bool]: The validator function.
    """
    # check if config has the field
    field = next(f for f in fields(Config) if f.name == key)
    if field is None:
        raise ValueError(f"Invalid configuration key: {key}")

    if key not in validators:
        validators[key] = []
    validators[key].append(validator)


def _load_config(config_file: str) -> Config:
    try:
        with open(config_file, "r") as file:
            return Config(**json.load(file))
    except FileNotFoundError:
        LOGGER.warning("Configuration file not found. Creating new file")
        return _store_config(Config())
    except Exception as e:
        LOGGER.exception(f"Error loading configuration: {e}")
        LOGGER.warning("Using default configuration")
        return Config()
    finally:
        LOGGER.debug("Configuration loaded")


def _store_config(config: Config) -> Config:
    try:
        with open(config_file, "w") as file:
            json.dump(asdict(config), file, indent=4)
        return config
    except Exception as e:
        LOGGER.exception(f"Error storing configuration: {e}")
        return config
    finally:
        LOGGER.debug("Configuration stored")


class ValidationError(Exception):
    """A configuration validation error."""

    ...


LOGGER.info("Configurator service started")
LOGGER.warning(f"Configuration file: {config_file}")
config = _load_config(config_file)
LOGGER.debug(f"Loaded config: {config}")
