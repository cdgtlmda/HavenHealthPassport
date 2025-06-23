#!/usr/bin/env python3
"""Translation Extraction CLI.

Command-line interface for the translation extraction tools.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional

import click

from src.translation.management.extraction_tools import (
    TranslationExtractor,
)
from src.utils.logging import get_logger

logger = get_logger(__name__)


@click.group()
def cli() -> None:
    """Haven Health Passport Translation Extraction Tools."""
    pass  # pylint: disable=unnecessary-pass


@cli.command()
@click.option(
    "--project-root",
    "-p",
    default=".",
    help="Project root directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--include",
    "-i",
    multiple=True,
    help="Paths to include (can be specified multiple times)",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Paths to exclude (can be specified multiple times)",
)
@click.option(
    "--output", "-o", help="Output directory for extraction report", type=click.Path()
)
def extract(
    project_root: str, include: tuple, exclude: tuple, output: Optional[str]
) -> None:
    """Extract all translatable strings from the project."""
    click.echo(f"Extracting translations from: {project_root}")

    extractor = TranslationExtractor(project_root)

    # Convert tuples to lists
    include_paths = list(include) if include else None
    exclude_paths = list(exclude) if exclude else None

    # Perform extraction
    result = extractor.extract_all(include_paths, exclude_paths)

    # Display results
    click.echo("\nExtraction complete:")
    click.echo(f"  Files processed: {result.files_processed}")
    click.echo(f"  Total strings: {result.total_strings}")
    click.echo(f"  New strings: {result.new_strings}")
    click.echo(f"  Updated strings: {result.updated_strings}")
    click.echo(f"  Removed strings: {result.removed_strings}")
    click.echo(f"  Errors: {len(result.errors)}")
    click.echo(f"  Time: {result.extraction_time:.2f}s")

    if result.errors:
        click.echo("\nErrors encountered:")
        for error in result.errors[:5]:  # Show first 5 errors
            click.echo(f"  - {error['file']}: {error['error']}")
        if len(result.errors) > 5:
            click.echo(f"  ... and {len(result.errors) - 5} more")

    # Generate detailed report
    if output:
        report = extractor.generate_extraction_report()
        report["extraction_result"] = {
            "files_processed": result.files_processed,
            "total_strings": result.total_strings,
            "new_strings": result.new_strings,
            "updated_strings": result.updated_strings,
            "removed_strings": result.removed_strings,
            "errors": result.errors,
            "extraction_time": result.extraction_time,
        }

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        click.echo(f"\nDetailed report saved to: {output_path}")


@cli.command()
@click.option(
    "--project-root",
    "-p",
    default=".",
    help="Project root directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option(
    "--output",
    "-o",
    required=True,
    help="Output directory for translation files",
    type=click.Path(),
)
@click.option(
    "--languages",
    "-l",
    multiple=True,
    required=True,
    help="Target languages (can be specified multiple times)",
)
@click.option(
    "--include-empty/--no-include-empty",
    default=True,
    help="Include empty strings in non-source languages",
)
def generate(
    project_root: str, output: str, languages: tuple, include_empty: bool
) -> None:
    """Generate translation JSON files for specified languages."""
    click.echo("Generating translation files...")

    extractor = TranslationExtractor(project_root)

    # Extract strings first
    result = extractor.extract_all()
    click.echo(f"Extracted {result.total_strings} strings")

    # Generate files
    extractor.generate_translation_files(output, list(languages), include_empty)

    click.echo(f"\nGenerated translation files for: {', '.join(languages)}")
    click.echo(f"Output directory: {output}")


@cli.command()
@click.option(
    "--project-root",
    "-p",
    default=".",
    help="Project root directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
def validate(project_root: str) -> None:
    """Validate translation strings for issues."""
    click.echo(f"Validating translations in: {project_root}")

    extractor = TranslationExtractor(project_root)

    # Extract strings
    result = extractor.extract_all()
    click.echo(f"Found {result.total_strings} strings")

    # Validate placeholders
    issues = extractor.validate_placeholders()

    if issues:
        click.echo(f"\nFound {len(issues)} placeholder issues:")
        for issue in issues:
            click.echo(f"  - {issue['key']} ({issue['file']}:{issue['line']})")
            click.echo(f"    {issue['issue']}")
    else:
        click.echo("\nNo placeholder issues found ✓")

    # Check for unused translations
    unused = extractor.find_unused_translations()

    if unused:
        click.echo(f"\nFound {len(unused)} unused translations:")
        for key in unused[:10]:  # Show first 10
            click.echo(f"  - {key}")
        if len(unused) > 10:
            click.echo(f"  ... and {len(unused) - 10} more")
    else:
        click.echo("\nNo unused translations found ✓")


@cli.command()
@click.option(
    "--project-root",
    "-p",
    default=".",
    help="Project root directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
)
@click.option("--language", "-l", required=True, help="Language code to check")
def check_missing(project_root: str, language: str) -> None:
    """Check for missing translations in a specific language."""
    click.echo(f"Checking missing translations for: {language}")

    extractor = TranslationExtractor(project_root)

    # Extract strings
    _ = extractor.extract_all()

    # Find missing translations
    missing = extractor.find_missing_translations(language)

    if missing:
        click.echo(f"\nFound {len(missing)} missing translations:")

        # Group by namespace
        by_namespace: Dict[str, List[str]] = {}
        for key in missing:
            namespace = key.split(".")[0] if "." in key else "common"
            if namespace not in by_namespace:
                by_namespace[namespace] = []
            by_namespace[namespace].append(key)

        for namespace, keys in by_namespace.items():
            click.echo(f"\n  {namespace} ({len(keys)} strings):")
            for key in keys[:5]:  # Show first 5 per namespace
                click.echo(f"    - {key}")
            if len(keys) > 5:
                click.echo(f"    ... and {len(keys) - 5} more")
    else:
        click.echo(f"\nAll translations present for {language} ✓")


if __name__ == "__main__":
    cli()
