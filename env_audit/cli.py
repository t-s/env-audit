from pathlib import Path
from typing import Annotated

import typer
import yaml

app = typer.Typer()


def parse_env_file(path: Path) -> dict[str, str]:
    env_vars = {}
    content = path.read_text()

    for line_num, line in enumerate(content.splitlines(), start=1):
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            raise typer.BadParameter(f"Invalid syntax at line {line_num}: {line}")

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        env_vars[key] = value

    return env_vars


def load_schema(path: Path) -> dict:
    content = path.read_text()
    return yaml.safe_load(content) or {}


def validate_type(value: str, expected_type: str) -> bool:
    if expected_type == "string":
        return True
    elif expected_type == "int":
        try:
            int(value)
            return True
        except ValueError:
            return False
    elif expected_type == "bool":
        return value.lower() in ("true", "false", "1", "0", "yes", "no")
    return True


def validate_env(env_vars: dict[str, str], schema: dict) -> list[str]:
    errors = []

    for var_name, rules in schema.items():
        is_required = rules.get("required", False)
        expected_type = rules.get("type", "string")
        value = env_vars.get(var_name)

        if value is None:
            if is_required:
                errors.append(f"Missing required variable: {var_name}")
            continue

        if not validate_type(value, expected_type):
            errors.append(f"{var_name}: expected {expected_type}, got '{value}'")

    return errors


@app.command()
def check(
    env_file: Annotated[Path, typer.Argument(help="Path to the .env file")],
    schema: Annotated[Path, typer.Option("--schema", "-s", help="Path to the YAML schema file")],
) -> None:
    if not env_file.exists():
        typer.echo(f"Error: {env_file} not found", err=True)
        raise typer.Exit(1)

    if not schema.exists():
        typer.echo(f"Error: {schema} not found", err=True)
        raise typer.Exit(1)

    try:
        env_vars = parse_env_file(env_file)
        schema_data = load_schema(schema)
        errors = validate_env(env_vars, schema_data)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    if errors:
        typer.echo("Validation failed:")
        for error in errors:
            typer.echo(f"  • {error}")
        raise typer.Exit(1)

    typer.echo("✓ Validation passed")
