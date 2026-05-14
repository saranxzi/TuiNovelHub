"""
User-Specific Configuration Management System.

This module provides comprehensive user configuration management including:
- User preference discovery and loading
- Configuration validation and merging
- Cross-platform config directory support
- Atomic configuration saving with backups
"""

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """User preferences data structure."""

    # Font preferences
    font_family: str = "bitter"
    font_fallback: str = "bitter"

    # Logging preferences
    log_level: str = "WARNING"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None

    # Directory preferences
    output_directory: Optional[str] = None
    input_directory: Optional[str] = None
    working_directory: Optional[str] = None
    auto_create_dirs: bool = True

    # EPUB generator preferences
    preferred_generator: str = "pandoc"  # pandoc or ebooklib
    fallback_enabled: bool = True
    include_toc: bool = True
    epub_compression: bool = False

    # Processing preferences
    max_workers: int = 10
    rate_limit: float = 0.5
    timeout: int = 30

    # Provider-specific preferences
    provider_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Image preferences
    download_covers: bool = True
    image_quality: int = 85
    image_format: str = "JPEG"

    # Database preferences
    database_path: Optional[str] = None  # Path to SQLite database file
    enable_database: bool = True  # Enable persistent storage
    auto_sync_filesystem: bool = True  # Automatically sync with filesystem
    database_backup_enabled: bool = True  # Enable automatic database backups

    # Cache preferences
    cache_enabled: bool = True  # Enable HTTP response caching
    cache_directory: Optional[str] = None  # Cache directory path
    cache_size_limit: str = "1GB"  # Maximum cache size
    cache_default_ttl: int = 3600  # Default cache TTL in seconds
    cache_compression: bool = True  # Enable cache compression
    cache_respect_headers: bool = True  # Honor HTTP cache headers
    cache_provider_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_cache_config(self):
        """Get cache configuration from user preferences."""
        from .cache_config import CacheConfig, ProviderCacheConfig

        # Convert provider settings
        providers = {}
        for provider_name, settings in self.cache_provider_settings.items():
            providers[provider_name] = ProviderCacheConfig(**settings)

        return CacheConfig(
            enabled=self.cache_enabled,
            directory=self.cache_directory,
            size_limit=self.cache_size_limit,
            default_ttl=self.cache_default_ttl,
            compression=self.cache_compression,
            respect_cache_headers=self.cache_respect_headers,
            providers=providers,
        )


class UserConfigManager:
    """Manages user-specific configuration with cross-platform support."""

    def __init__(self):
        """Initialize user configuration manager."""
        self.config_dirs = self._get_config_directories()
        self.config_file_name = "config.yaml"
        self.backup_suffix = ".backup"
        self._user_config: Optional[Dict[str, Any]] = None
        self._preferences: Optional[UserPreferences] = None

        logger.debug(f"UserConfigManager initialized, config dirs: {self.config_dirs}")

    def _get_config_directories(self) -> List[Path]:
        """Get list of configuration directories in priority order."""
        dirs = []

        # XDG Base Directory Specification (Linux/Unix)
        if os.name == "posix":
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                dirs.append(Path(xdg_config) / "wn-dl")
            else:
                dirs.append(Path.home() / ".config" / "wn-dl")

            # Alternative: simple home directory
            dirs.append(Path.home() / ".wn-dl")

        # Windows
        elif os.name == "nt":
            appdata = os.environ.get("APPDATA")
            if appdata:
                dirs.append(Path(appdata) / "wn-dl")

            # Fallback to user profile
            dirs.append(Path.home() / ".wn-dl")

        # macOS (follows XDG but with macOS conventions)
        else:
            dirs.append(Path.home() / "Library" / "Application Support" / "wn-dl")
            dirs.append(Path.home() / ".config" / "wn-dl")
            dirs.append(Path.home() / ".wn-dl")

        return dirs

    def get_config_file_path(self, create_if_missing: bool = False) -> Optional[Path]:
        """
        Get the path to the user configuration file.

        Args:
            create_if_missing: Create config directory if it doesn't exist

        Returns:
            Path to config file or None if not found and not creating
        """
        # Check existing config files in priority order
        for config_dir in self.config_dirs:
            config_file = config_dir / self.config_file_name
            if config_file.exists():
                return config_file

        # If creating, use the first (highest priority) directory
        if create_if_missing and self.config_dirs:
            config_dir = self.config_dirs[0]
            config_dir.mkdir(parents=True, exist_ok=True)
            return config_dir / self.config_file_name

        return None

    def load_user_config(self) -> Dict[str, Any]:
        """
        Load user configuration from file.

        Returns:
            User configuration dictionary
        """
        if self._user_config is not None:
            return self._user_config

        config_file = self.get_config_file_path()
        if not config_file or not config_file.exists():
            logger.debug("No user configuration file found, using defaults")
            self._user_config = {}
            return self._user_config

        try:
            with open(config_file, "r", encoding="utf-8") as f:
                self._user_config = yaml.safe_load(f) or {}

            logger.debug(f"Loaded user configuration from: {config_file}")
            return self._user_config

        except Exception as e:
            logger.error(f"Error loading user configuration: {e}")
            self._user_config = {}
            return self._user_config

    def save_user_config(
        self, config: Dict[str, Any], create_backup: bool = True
    ) -> bool:
        """
        Save user configuration to file with atomic write and backup.

        Args:
            config: Configuration dictionary to save
            create_backup: Create backup of existing config

        Returns:
            True if saved successfully
        """
        try:
            config_file = self.get_config_file_path(create_if_missing=True)
            if not config_file:
                logger.error("Could not determine config file path")
                return False

            # Create backup if file exists
            if create_backup and config_file.exists():
                backup_file = config_file.with_suffix(
                    config_file.suffix + self.backup_suffix
                )
                shutil.copy2(config_file, backup_file)
                logger.debug(f"Created backup: {backup_file}")

            # Atomic write using temporary file
            temp_file = config_file.with_suffix(config_file.suffix + ".tmp")

            with open(temp_file, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=True, indent=2)

            # Atomic move
            temp_file.replace(config_file)

            # Update cached config
            self._user_config = config
            self._preferences = None  # Reset preferences cache

            logger.info(f"Saved user configuration to: {config_file}")
            return True

        except Exception as e:
            logger.error(f"Error saving user configuration: {e}")
            return False

    def get_preferences(self) -> UserPreferences:
        """
        Get user preferences with defaults.

        Returns:
            UserPreferences object with user settings or defaults
        """
        if self._preferences is not None:
            return self._preferences

        config = self.load_user_config()
        prefs_dict = config.get("preferences", {})

        # Create preferences with defaults, overridden by user settings
        self._preferences = UserPreferences(
            # Font preferences
            font_family=prefs_dict.get("font", {}).get("default_family", "bitter"),
            font_fallback=prefs_dict.get("font", {}).get("fallback_family", "bitter"),
            # Logging preferences
            log_level=prefs_dict.get("logging", {}).get("level", "WARNING"),
            log_format=prefs_dict.get("logging", {}).get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            log_file=prefs_dict.get("logging", {}).get("file"),
            # Directory preferences
            output_directory=prefs_dict.get("output_directory")
            or prefs_dict.get("directories", {}).get("output"),
            input_directory=prefs_dict.get("input_directory")
            or prefs_dict.get("directories", {}).get("input"),
            working_directory=prefs_dict.get("working_directory")
            or prefs_dict.get("directories", {}).get("working"),
            auto_create_dirs=prefs_dict.get(
                "auto_create_dirs",
                prefs_dict.get("directories", {}).get("auto_create", True),
            ),
            # EPUB generator preferences
            preferred_generator=prefs_dict.get("epub", {}).get(
                "preferred_generator", "pandoc"
            ),
            fallback_enabled=prefs_dict.get("epub", {}).get("fallback_enabled", True),
            include_toc=prefs_dict.get("epub", {}).get("include_toc", True),
            epub_compression=prefs_dict.get("epub", {}).get("compression", False),
            # Processing preferences
            max_workers=prefs_dict.get("processing", {}).get("max_workers", 10),
            rate_limit=prefs_dict.get("processing", {}).get("rate_limit", 0.5),
            timeout=prefs_dict.get("processing", {}).get("timeout", 30),
            # Provider preferences
            provider_settings=prefs_dict.get("providers", {}),
            # Image preferences
            download_covers=prefs_dict.get("images", {}).get("download_covers", True),
            image_quality=prefs_dict.get("images", {}).get("quality", 85),
            image_format=prefs_dict.get("images", {}).get("format", "JPEG"),
            # Database preferences
            database_path=prefs_dict.get("database", {}).get("path", None),
            enable_database=prefs_dict.get("database", {}).get("enabled", True),
            auto_sync_filesystem=prefs_dict.get("database", {}).get("auto_sync", True),
            database_backup_enabled=prefs_dict.get("database", {}).get(
                "backup_enabled", True
            ),
            # Cache preferences
            cache_enabled=prefs_dict.get("cache", {}).get("enabled", True),
            cache_directory=prefs_dict.get("cache", {}).get("directory", None),
            cache_size_limit=prefs_dict.get("cache", {}).get("size_limit", "1GB"),
            cache_default_ttl=prefs_dict.get("cache", {}).get("default_ttl", 3600),
            cache_compression=prefs_dict.get("cache", {}).get("compression", True),
            cache_respect_headers=prefs_dict.get("cache", {}).get(
                "respect_headers", True
            ),
            cache_provider_settings=prefs_dict.get("cache", {}).get("providers", {}),
        )

        return self._preferences

    def set_preference(self, key: str, value: Any) -> bool:
        """
        Set a user preference value.

        Args:
            key: Preference key (e.g., 'font.default_family', 'logging.level')
            value: Preference value

        Returns:
            True if set successfully
        """
        try:
            config = self.load_user_config()

            # Ensure preferences section exists
            if "preferences" not in config:
                config["preferences"] = {}

            # Parse nested key (e.g., 'font.default_family')
            keys = key.split(".")
            current = config["preferences"]

            # Navigate to parent of target key
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]

            # Set the value
            current[keys[-1]] = value

            # Save configuration
            success = self.save_user_config(config)
            if success:
                logger.info(f"Set preference {key} = {value}")

            return success

        except Exception as e:
            logger.error(f"Error setting preference {key}: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """
        Reset user configuration to defaults.

        Returns:
            True if reset successfully
        """
        try:
            default_config = {
                "preferences": {
                    "font": {"default_family": "bitter", "fallback_family": "bitter"},
                    "logging": {
                        "level": "WARNING",
                        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    },
                    "directories": {"auto_create": True},
                    "epub": {
                        "preferred_generator": "pandoc",
                        "fallback_enabled": True,
                        "include_toc": True,
                        "compression": False,
                    },
                    "processing": {"max_workers": 10, "rate_limit": 0.5, "timeout": 30},
                    "images": {
                        "download_covers": True,
                        "quality": 85,
                        "format": "JPEG",
                    },
                    "cache": {
                        "enabled": True,
                        "size_limit": "1GB",
                        "default_ttl": 3600,
                        "compression": True,
                        "respect_headers": True,
                    },
                }
            }

            success = self.save_user_config(default_config)
            if success:
                logger.info("Reset user configuration to defaults")

            return success

        except Exception as e:
            logger.error(f"Error resetting configuration: {e}")
            return False


# Global user config manager instance
_user_config_manager: Optional[UserConfigManager] = None


def get_user_config_manager() -> UserConfigManager:
    """Get the global user configuration manager instance."""
    global _user_config_manager
    if _user_config_manager is None:
        _user_config_manager = UserConfigManager()
    return _user_config_manager


def get_user_preferences() -> UserPreferences:
    """Convenience function to get user preferences."""
    return get_user_config_manager().get_preferences()


def set_user_preference(key: str, value: Any) -> bool:
    """Convenience function to set a user preference."""
    return get_user_config_manager().set_preference(key, value)


def reset_user_config() -> bool:
    """Convenience function to reset user configuration."""
    return get_user_config_manager().reset_to_defaults()


def merge_configurations(
    user_config: Dict[str, Any],
    project_config: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Merge configurations with precedence: user > project > defaults.

    Args:
        user_config: User-specific configuration
        project_config: Project-specific configuration
        defaults: Default configuration

    Returns:
        Merged configuration dictionary
    """

    def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    # Start with defaults, then merge project config, then user config
    merged = defaults.copy()
    merged = deep_merge(merged, project_config)
    merged = deep_merge(merged, user_config)

    return merged


def get_effective_config(project_config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get effective configuration by merging user, project, and default configs.

    Args:
        project_config_path: Path to project configuration file

    Returns:
        Effective configuration dictionary
    """
    from ..config import get_config

    # Get user configuration
    user_config_manager = get_user_config_manager()
    user_config = user_config_manager.load_user_config()

    # Get project configuration
    if project_config_path:
        try:
            with open(project_config_path, "r", encoding="utf-8") as f:
                project_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Could not load project config {project_config_path}: {e}")
            project_config = {}
    else:
        # Use existing project config loading
        project_config = get_config()

    # Get default configuration
    defaults = {
        "epub": {
            "chapter_level": 2,
            "include_toc": True,
            "custom_css": True,
            "use_ebooklib": False,
            "font_family": "bitter",
        },
        "processing": {"max_workers": 10, "rate_limit": 0.5, "timeout": 30},
        "logging": {
            "level": "WARNING",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "images": {"download_covers": True, "quality": 85, "format": "JPEG"},
    }

    # Merge configurations
    effective_config = merge_configurations(user_config, project_config, defaults)

    logger.debug("Merged user, project, and default configurations")
    return effective_config
