"""
Provider registry for managing web novel scrapers.

This module provides a registry system for discovering and loading provider-specific scrapers.
"""

import logging
from typing import Dict, List, Optional, Type
from urllib.parse import urlparse

from ..core.base_scraper import BaseNovelScraper
from ..core.cache_config import CacheConfig

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Registry for managing web novel scraper providers.

    Provides functionality to register, discover, and instantiate provider-specific scrapers.
    """

    def __init__(self):
        """Initialize the provider registry."""
        self._providers: Dict[str, Type[BaseNovelScraper]] = {}
        self._domain_mappings: Dict[str, str] = {}

        logger.debug("ProviderRegistry initialized")

    def register(
        self,
        name: str,
        scraper_class: Type[BaseNovelScraper],
        domains: Optional[List[str]] = None,
    ) -> None:
        """
        Register a provider scraper.

        Args:
            name: Provider name (e.g., 'novelbin')
            scraper_class: Scraper class that inherits from BaseNovelScraper
            domains: List of domains this provider handles
        """
        if not issubclass(scraper_class, BaseNovelScraper):
            raise ValueError(f"Scraper class must inherit from BaseNovelScraper")

        self._providers[name] = scraper_class

        # Register domain mappings
        if domains:
            for domain in domains:
                self._domain_mappings[domain] = name

        logger.info(f"Registered provider '{name}' with domains: {domains}")

    def unregister(self, name: str) -> None:
        """
        Unregister a provider.

        Args:
            name: Provider name to unregister
        """
        if name in self._providers:
            del self._providers[name]

            # Remove domain mappings
            domains_to_remove = [
                domain
                for domain, provider in self._domain_mappings.items()
                if provider == name
            ]
            for domain in domains_to_remove:
                del self._domain_mappings[domain]

            logger.info(f"Unregistered provider '{name}'")
        else:
            logger.warning(f"Provider '{name}' not found in registry")

    def get_provider_class(self, name: str) -> Optional[Type[BaseNovelScraper]]:
        """
        Get provider class by name.

        Args:
            name: Provider name

        Returns:
            Provider class or None if not found
        """
        return self._providers.get(name)

    def get_provider_for_url(self, url: str) -> Optional[str]:
        """
        Get provider name for a given URL.

        Args:
            url: URL to check

        Returns:
            Provider name or None if no provider found
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Try exact domain match first
            if domain in self._domain_mappings:
                return self._domain_mappings[domain]

            # Try subdomain matching
            for registered_domain, provider in self._domain_mappings.items():
                if (
                    domain.endswith(f".{registered_domain}")
                    or domain == registered_domain
                ):
                    return provider

            logger.debug(f"No provider found for domain: {domain}")
            return None

        except Exception as e:
            logger.error(f"Error parsing URL '{url}': {e}")
            return None

    def create_scraper(
        self,
        provider_name: str,
        config: Dict,
        cache_config: Optional[CacheConfig] = None,
    ) -> Optional[BaseNovelScraper]:
        """
        Create a scraper instance for the given provider.

        Args:
            provider_name: Name of the provider
            config: Configuration dictionary for the scraper
            cache_config: Optional cache configuration

        Returns:
            Scraper instance or None if provider not found
        """
        scraper_class = self.get_provider_class(provider_name)
        if scraper_class is None:
            logger.error(f"Provider '{provider_name}' not found in registry")
            return None

        try:
            return scraper_class(config, cache_config=cache_config)
        except Exception as e:
            logger.error(
                f"Failed to create scraper for provider '{provider_name}': {e}"
            )
            return None

    def create_scraper_for_url(
        self, url: str, config: Dict, cache_config: Optional[CacheConfig] = None
    ) -> Optional[BaseNovelScraper]:
        """
        Create a scraper instance for the given URL.

        Args:
            url: URL to scrape
            config: Configuration dictionary for the scraper
            cache_config: Optional cache configuration

        Returns:
            Scraper instance or None if no suitable provider found
        """
        provider_name = self.get_provider_for_url(url)
        if provider_name is None:
            logger.error(f"No provider found for URL: {url}")
            return None

        return self.create_scraper(provider_name, config, cache_config)

    def list_providers(self) -> List[str]:
        """
        Get list of registered provider names.

        Returns:
            List of provider names
        """
        return list(self._providers.keys())

    def list_supported_domains(self) -> List[str]:
        """
        Get list of supported domains.

        Returns:
            List of domain names
        """
        return list(self._domain_mappings.keys())

    def get_provider_info(self, name: str) -> Optional[Dict]:
        """
        Get information about a provider.

        Args:
            name: Provider name

        Returns:
            Provider information dictionary or None if not found
        """
        scraper_class = self.get_provider_class(name)
        if scraper_class is None:
            return None

        # Get domains for this provider
        domains = [
            domain
            for domain, provider in self._domain_mappings.items()
            if provider == name
        ]

        return {
            "name": name,
            "class": scraper_class.__name__,
            "module": scraper_class.__module__,
            "domains": domains,
            "docstring": scraper_class.__doc__,
        }

    def validate_provider(self, name: str) -> List[str]:
        """
        Validate a provider implementation.

        Args:
            name: Provider name to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        scraper_class = self.get_provider_class(name)
        if scraper_class is None:
            errors.append(f"Provider '{name}' not found")
            return errors

        # Check required methods are implemented
        required_methods = [
            "get_novel_metadata",
            "get_chapter_list",
            "scrape_chapter_content",
            "get_provider_name",
        ]

        for method_name in required_methods:
            if not hasattr(scraper_class, method_name):
                errors.append(f"Missing required method: {method_name}")
            else:
                method = getattr(scraper_class, method_name)
                if not callable(method):
                    errors.append(f"Method {method_name} is not callable")

        # Check if class properly inherits from BaseNovelScraper
        if not issubclass(scraper_class, BaseNovelScraper):
            errors.append("Provider class must inherit from BaseNovelScraper")

        return errors


# Global registry instance
registry = ProviderRegistry()


def register_provider(
    name: str,
    scraper_class: Type[BaseNovelScraper],
    domains: Optional[List[str]] = None,
) -> None:
    """
    Register a provider in the global registry.

    Args:
        name: Provider name
        scraper_class: Scraper class
        domains: List of domains this provider handles
    """
    registry.register(name, scraper_class, domains)


def get_scraper_for_url(
    url: str, config: Dict, cache_config: Optional[CacheConfig] = None
) -> Optional[BaseNovelScraper]:
    """
    Get a scraper instance for the given URL.

    Args:
        url: URL to scrape
        config: Configuration dictionary
        cache_config: Optional cache configuration

    Returns:
        Scraper instance or None if no suitable provider found
    """
    return registry.create_scraper_for_url(url, config, cache_config)


def list_providers() -> List[str]:
    """Get list of registered providers."""
    return registry.list_providers()


def list_supported_domains() -> List[str]:
    """Get list of supported domains."""
    return registry.list_supported_domains()
