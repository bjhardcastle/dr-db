#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "pydantic-settings>=2.14.1",
# ]
# ///

"""Demonstrate the CLI spellings accepted by pydantic-settings.

Try both forms:

    uv run --script scripts/pydantic_settings_cli_demo.py --example-value kebab
    uv run --script scripts/pydantic_settings_cli_demo.py --example_value underscore
"""

from pydantic_settings import BaseSettings


class Settings(
    BaseSettings,
    cli_parse_args=True,
    cli_kebab_case="all",
    cli_shortcuts={"example-value": "example_value"},
):
    example_value: str


def main() -> None:
    settings = Settings()
    print(f"example_value={settings.example_value}")


if __name__ == "__main__":
    main()
