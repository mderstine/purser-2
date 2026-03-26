#!/usr/bin/env python3
"""
Hello World Program in 5 Languages

A simple CLI that greets users in multiple languages.
Demonstrates basic internationalization without external dependencies.
"""

import argparse
import sys

# Language database: code -> (language_name, greeting)
LANGUAGES = {
    "en": ("English", "Hello!"),
    "es": ("Spanish", "¡Hola!"),
    "fr": ("French", "Bonjour!"),
    "de": ("German", "Hallo!"),
    "ja": ("Japanese", "こんにちは!"),
}


def greet(languages: list[str] | None = None) -> None:
    """
    Print greetings in specified languages.

    Args:
        languages: List of language codes to display. If None, uses all.
    """
    if languages is None:
        # Display all languages in default order
        languages = ["en", "es", "fr", "de", "ja"]

    print("🌍 Greetings from around the world:\n")

    for code in languages:
        if code in LANGUAGES:
            lang_name, greeting = LANGUAGES[code]
            print(f"  {lang_name:12} {greeting}")
        else:
            print(f"  [Unknown language code: {code}]")

    print()  # Trailing newline


def main() -> int:
    """
    Main entry point for the CLI.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Greet the world in multiple languages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available languages:
  en - English    es - Spanish
  fr - French     de - German
  ja - Japanese

Examples:
  python hello.py              # Show all 5 languages
  python hello.py --languages en es  # Show only English and Spanish
        """,
    )

    parser.add_argument(
        "--languages",
        "-l",
        nargs="+",
        metavar="CODE",
        help="Language codes to display (default: all 5 languages)",
    )

    args = parser.parse_args()

    try:
        greet(args.languages)
        return 0
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 130


if __name__ == "__main__":
    sys.exit(main())
