# Translation Extraction Tools

Tools for extracting and managing translatable strings in Haven Health Passport.

## Quick Start

```bash
# Extract all strings
python -m src.translation.management.extract_cli extract --output report.json

# Generate translation files
python -m src.translation.management.extract_cli generate \
  --output public/locales \
  --languages en --languages es --languages fr --languages ar

# Validate translations
python -m src.translation.management.extract_cli validate

# Check missing translations
python -m src.translation.management.extract_cli check-missing --language es
```

## Features

- Automatic extraction from TS/JS/Python files
- Multi-framework support (i18next, React, gettext)
- Medical term detection
- Namespace organization
- Placeholder validation
- Missing translation detection

## Supported Patterns

**React/TypeScript**: `t('key')`, `<Trans>`, `i18n.t()`, `translate()`  
**Python**: `_('key')`, `gettext()`, `medical_translate()`

## Testing

```bash
pytest tests/translation/management/test_extraction_tools.py -v
```
