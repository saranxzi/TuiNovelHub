# 🤝 Contributing to wn-dl

Thank you for your interest in contributing to wn-dl! This guide will help you get started with contributing to the project.

## 🚀 Quick Start

### Development Setup

```bash
# 1. Fork and clone the repository
git clone https://github.com/wongpinter/webnovel-scraper.git
cd webnovel-scraper

# 2. Install with development dependencies
uv sync  # Recommended
# OR
pip install -e ".[dev]"

# 3. Install pre-commit hooks
pre-commit install

# 4. Run tests to verify setup
pytest
```

### Making Changes

```bash
# 1. Create a feature branch
git checkout -b feature/your-feature-name

# 2. Make your changes
# ... edit files ...

# 3. Run tests and linting
pytest
black src/ tests/
flake8 src/ tests/

# 4. Commit your changes
git add .
git commit -m "feat: add your feature description"

# 5. Push and create pull request
git push origin feature/your-feature-name
```

## 📋 Types of Contributions

### 🐛 Bug Reports

When reporting bugs, please include:

1. **Clear description** of the issue
2. **Steps to reproduce** the problem
3. **Expected vs actual behavior**
4. **System information** (`wn-dl info`)
5. **Error logs** with `--with-info` flag

**Template**:

```markdown

## Bug Description

Brief description of the issue

## Steps to Reproduce

1. Run command: `wn-dl scrape -u URL`
2. Observe error: ...

## Expected Behavior

What should happen

## Actual Behavior

What actually happens

## System Information

```

wn-dl info

```

## Error Logs

```

wn-dl --with-info scrape -u URL

```
```

### ✨ Feature Requests

For new features, please:

1. **Check existing issues** to avoid duplicates
2. **Describe the use case** and motivation
3. **Propose implementation** if you have ideas
4. **Consider backwards compatibility**

### 🔌 New Providers

Adding support for new novel sites:

1. **Follow the [Provider Development Guide](PROVIDER_DEVELOPMENT.md)**
2. **Test thoroughly** with multiple novels
3. **Include configuration file**
4. **Add documentation**

### 📚 Documentation

Documentation improvements are always welcome:

1. **Fix typos and grammar**
2. **Add examples and clarifications**
3. **Update outdated information**
4. **Translate to other languages**

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_epub_generator.py

# Run with coverage
pytest --cov=wn_dl

# Run integration tests (slower)
pytest tests/integration/
```

### Writing Tests

#### Unit Tests

```python
# tests/unit/test_new_feature.py
import pytest
from wn_dl.core.new_feature import NewFeature

def test_new_feature():
    """Test new feature functionality."""
    feature = NewFeature()
    result = feature.do_something()
    assert result == expected_value

@pytest.mark.asyncio
async def test_async_feature():
    """Test async functionality."""
    feature = NewFeature()
    result = await feature.async_method()
    assert result is not None
```

#### Integration Tests

```python
# tests/integration/test_provider.py
import pytest
from wn_dl.providers.mysite.scraper import MySiteScraper

@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_integration():
    """Test provider with real website."""
    scraper = MySiteScraper(config)
    novel_info = await scraper.get_novel_info(test_url)
    assert novel_info.title
    assert novel_info.author
```

### Test Guidelines

1. **Write tests for new features**
2. **Maintain test coverage above 80%**
3. **Use descriptive test names**
4. **Mock external dependencies**
5. **Test edge cases and error conditions**

## 📝 Code Style

### Python Style Guide

We follow [PEP 8](https://pep8.org/) with some modifications:

```python
# Good
class NovelScraper:
    """Scraper for web novels."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    async def get_novel_info(self, url: str) -> Optional[NovelInfo]:
        """Extract novel information from URL."""
        try:
            soup = await self.get_soup(url)
            return self._parse_novel_info(soup)
        except Exception as e:
            self.logger.error(f"Failed to get novel info: {e}")
            return None
```

### Formatting Tools

```bash
# Auto-format code
black src/ tests/

# Sort imports
isort src/ tests/

# Check style
flake8 src/ tests/

# Type checking
mypy src/
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Format: type(scope): description

# Examples:
git commit -m "feat(epub): add progress bar to EbookLib generator"
git commit -m "fix(scraper): handle rate limiting errors"
git commit -m "docs(readme): update installation instructions"
git commit -m "test(provider): add integration tests for NovelFull"
```

**Types**:
* `feat`: New feature
* `fix`: Bug fix
* `docs`: Documentation changes
* `test`: Adding or updating tests
* `refactor`: Code refactoring
* `perf`: Performance improvements
* `chore`: Maintenance tasks

## 🔄 Pull Request Process

### Before Submitting

1. **Update documentation** if needed
2. **Add tests** for new functionality
3. **Run full test suite**: `pytest`
4. **Check code style**: `black . && flake8`
5. **Update CHANGELOG.md** if applicable

### PR Template

```markdown

## Description

Brief description of changes

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Other (please describe)

## Testing

- [ ] Tests pass locally
- [ ] Added new tests for changes
- [ ] Manual testing completed

## Checklist

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

### Review Process

1. **Automated checks** must pass
2. **Code review** by maintainers
3. **Testing** on different platforms
4. **Documentation review**
5. **Merge** when approved

## 🏗️ Architecture Guidelines

### Project Structure

```
wn-dl/
├── src/wn_dl/           # Main package
│   ├── core/            # Core functionality
│   ├── providers/       # Site-specific scrapers
│   ├── templates/       # CSS and font files
│   └── utils.py         # Utility functions
├── tests/               # Test suite
├── docs/                # Documentation
├── config/              # Configuration files
└── scripts/             # Development scripts
```

### Design Principles

1. **Modularity**: Keep components loosely coupled
2. **Extensibility**: Easy to add new providers
3. **Reliability**: Robust error handling
4. **Performance**: Efficient for large novels
5. **Usability**: Simple CLI interface

### Adding New Features

1. **Design first**: Consider architecture impact
2. **Start small**: Implement MVP first
3. **Test thoroughly**: Unit and integration tests
4. **Document**: Update relevant documentation
5. **Get feedback**: Discuss with maintainers

## 🌍 Community Guidelines

### Code of Conduct

* **Be respectful** and inclusive
* **Help others** learn and contribute
* **Give constructive feedback**
* **Focus on the code**, not the person
* **Assume good intentions**

### Communication

* **GitHub Issues**: Bug reports and feature requests
* **Pull Requests**: Code contributions
* **Discussions**: General questions and ideas
* **Documentation**: Improve guides and examples

## 🎯 Good First Issues

Looking for ways to contribute? Try these:

### Easy

* Fix typos in documentation
* Add examples to existing guides
* Improve error messages
* Add unit tests for existing code

### Medium

* Implement new provider for a novel site
* Add new EPUB customization options
* Improve performance of existing features
* Add new CLI commands

### Hard

* Implement new EPUB generation features
* Add support for new output formats
* Optimize memory usage for large novels
* Add advanced provider features

## 📊 Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):

* **MAJOR**: Breaking changes
* **MINOR**: New features (backwards compatible)
* **PATCH**: Bug fixes

### Release Checklist

1. Update version in `pyproject.toml`
2. Update `CHANGELOG.md`
3. Run full test suite
4. Create release tag
5. Build and publish to PyPI
6. Update documentation

## 🙏 Recognition

Contributors are recognized in:

* **CHANGELOG.md**: Feature and fix credits
* **README.md**: Major contributors
* **GitHub**: Contributor graphs and statistics

## 📚 Resources

* **[Provider Development Guide](PROVIDER_DEVELOPMENT.md)**: Adding new sites
* **[Configuration Guide](CONFIGURATION.md)**: Understanding settings
* **[EPUB Generation Guide](EPUB_GENERATION.md)**: EPUB system details
* **[Troubleshooting Guide](TROUBLESHOOTING.md)**: Common issues

---

**Thank you for contributing to wn-dl!** 🎉

Your contributions help make web novel reading better for everyone.
