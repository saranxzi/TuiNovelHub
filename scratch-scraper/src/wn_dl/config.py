"""
Configuration management for the web novel scraper.

This module handles loading and validating configuration from YAML files.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when there's an error in configuration."""

    pass


class ConfigManager:
    """
    Manages configuration loading and validation.

    Supports hierarchical configuration with defaults, provider-specific settings,
    and user overrides.
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Directory containing configuration files
        """
        if config_dir is None:
            # Default to config directory relative to package
            package_dir = Path(__file__).parent.parent.parent
            config_dir = package_dir / "config"

        self.config_dir = Path(config_dir)
        self._config_cache: Dict[str, Dict[str, Any]] = {}

        logger.debug(f"ConfigManager initialized with config_dir: {self.config_dir}")

    def load_default_config(self) -> Dict[str, Any]:
        """
        Load default application configuration.

        Returns:
            Default configuration dictionary
        """
        return {
            "app": {
                "name": "wn-dl",
                "version": "0.1.0",
                "debug": False,
            },
            "output": {
                "directory": "./output",
                "formats": ["markdown", "epub"],
                "create_subdirs": True,
                "filename_template": "{title}",
            },
            "processing": {
                "max_workers": 10,
                "rate_limit": 0.5,
                "timeout": 30,
                "max_retries": 3,
                "chunk_size": 50,
            },
            "images": {
                "download_covers": True,
                "target_size": [600, 800],
                "quality": 85,
                "format": "JPEG",
                "create_placeholder": True,
            },
            "epub": {
                "chapter_level": 2,
                "include_toc": True,
                "custom_css": True,
                "use_ebooklib": False,  # Default to pandoc if available
                "pandoc_args": [],
                # Chapter title formatting options
                "chapter_title_format": "title_only",  # Options: title_only, number_title, chapter_number_title, number_only
                "chapter_number_format": "arabic",  # Options: arabic, roman, roman_upper
            },
            "logging": {
                "level": "WARNING",  # Default to silent (WARNING level)
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": None,
            },
        }

    def load_config_file(self, filename: str) -> Dict[str, Any]:
        """
        Load configuration from a YAML file.

        Args:
            filename: Name of the configuration file

        Returns:
            Configuration dictionary

        Raises:
            ConfigurationError: If file cannot be loaded or parsed
        """
        if filename in self._config_cache:
            return self._config_cache[filename]

        file_path = self.config_dir / filename

        if not file_path.exists():
            logger.warning(f"Configuration file not found: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}

            logger.debug(f"Loaded configuration from {file_path}")
            self._config_cache[filename] = config
            return config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse YAML file {file_path}: {e}")
        except Exception as e:
            raise ConfigurationError(
                f"Failed to load configuration file {file_path}: {e}"
            )

    def load_provider_config(self, provider_name: str) -> Dict[str, Any]:
        """
        Load provider-specific configuration.

        Args:
            provider_name: Name of the provider (e.g., 'novelbin')

        Returns:
            Provider configuration dictionary

        Raises:
            ConfigurationError: If provider config cannot be loaded
        """
        filename = f"{provider_name}-provider.yaml"
        config = self.load_config_file(filename)

        if not config:
            raise ConfigurationError(
                f"No configuration found for provider: {provider_name}"
            )

        # Validate required provider fields
        self._validate_provider_config(config, provider_name)

        return config

    def _validate_provider_config(
        self, config: Dict[str, Any], provider_name: str
    ) -> None:
        """
        Validate provider configuration.

        Args:
            config: Provider configuration dictionary
            provider_name: Name of the provider

        Raises:
            ConfigurationError: If configuration is invalid
        """
        required_sections = ["provider", "selectors", "request"]
        for section in required_sections:
            if section not in config:
                raise ConfigurationError(
                    f"Missing required section '{section}' in {provider_name} provider config"
                )

        # Validate provider section
        provider_section = config["provider"]
        required_provider_fields = ["name", "base_url"]
        for field in required_provider_fields:
            if field not in provider_section:
                raise ConfigurationError(
                    f"Missing required field '{field}' in provider section of {provider_name} config"
                )

        # Validate selectors section
        selectors = config["selectors"]
        required_selectors = [
            "title",
            "author",
            "description",
            "chapter_list",
            "chapter_content",
        ]
        for selector in required_selectors:
            if selector not in selectors:
                logger.warning(
                    f"Missing selector '{selector}' in {provider_name} provider config"
                )

    def merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge multiple configuration dictionaries.

        Later configurations override earlier ones.

        Args:
            *configs: Configuration dictionaries to merge

        Returns:
            Merged configuration dictionary
        """
        result = {}

        for config in configs:
            result = self._deep_merge(result, config)

        return result

    def _deep_merge(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            override: Override dictionary

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def get_app_config(self, user_config_file: Optional[str] = None) -> Dict[str, Any]:
        """
        Get complete application configuration.

        Merges default config with user overrides.

        Args:
            user_config_file: Optional user configuration file

        Returns:
            Complete application configuration
        """
        # Start with defaults
        config = self.load_default_config()

        # Load user config if specified
        if user_config_file:
            user_config = self.load_config_file(user_config_file)
            config = self.merge_configs(config, user_config)

        # Load environment-specific overrides
        env_config = self._load_env_config()
        if env_config:
            config = self.merge_configs(config, env_config)

        return config

    def _load_env_config(self) -> Dict[str, Any]:
        """
        Load configuration from environment variables.

        Returns:
            Configuration dictionary from environment variables
        """
        config = {}

        # Map environment variables to config paths
        env_mappings = {
            "WN_DL_OUTPUT_DIR": ["output", "directory"],
            "WN_DL_MAX_WORKERS": ["processing", "max_workers"],
            "WN_DL_RATE_LIMIT": ["processing", "rate_limit"],
            "WN_DL_DEBUG": ["app", "debug"],
            "WN_DL_LOG_LEVEL": ["logging", "level"],
        }

        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert value to appropriate type
                if config_path[-1] in ["max_workers"]:
                    value = int(value)
                elif config_path[-1] in ["rate_limit"]:
                    value = float(value)
                elif config_path[-1] in ["debug"]:
                    value = value.lower() in ["true", "1", "yes", "on"]

                # Set nested config value
                current = config
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                current[config_path[-1]] = value

        return config

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """
        Validate configuration and return list of warnings/errors.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation messages
        """
        messages = []

        # Validate output directory
        output_dir = config.get("output", {}).get("directory")
        if output_dir:
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messages.append(f"Cannot create output directory '{output_dir}': {e}")

        # Validate processing settings
        processing = config.get("processing", {})
        max_workers = processing.get("max_workers", 10)
        if max_workers < 1 or max_workers > 50:
            messages.append(
                f"max_workers should be between 1 and 50, got {max_workers}"
            )

        rate_limit = processing.get("rate_limit", 0.5)
        if rate_limit < 0:
            messages.append(f"rate_limit should be non-negative, got {rate_limit}")

        # Validate image settings
        images = config.get("images", {})
        target_size = images.get("target_size", [600, 800])
        if not isinstance(target_size, list) or len(target_size) != 2:
            messages.append(
                "target_size should be a list of two integers [width, height]"
            )

        quality = images.get("quality", 85)
        if quality < 1 or quality > 100:
            messages.append(f"image quality should be between 1 and 100, got {quality}")

        return messages


# Global configuration manager instance
config_manager = ConfigManager()


def get_config(user_config_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Get application configuration.

    Args:
        user_config_file: Optional user configuration file

    Returns:
        Application configuration dictionary
    """
    return config_manager.get_app_config(user_config_file)


def get_provider_config(provider_name: str) -> Dict[str, Any]:
    """
    Get provider-specific configuration.

    Args:
        provider_name: Name of the provider

    Returns:
        Provider configuration dictionary
    """
    return config_manager.load_provider_config(provider_name)
