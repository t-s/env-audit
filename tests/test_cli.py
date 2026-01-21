import pytest
from pathlib import Path
from typer.testing import CliRunner

from env_audit.cli import (
    app,
    parse_env_file,
    load_schema,
    validate_type,
    validate_env,
)

runner = CliRunner()


class TestParseEnvFile:
    def test_simple_vars(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar\nBAZ=123")
        result = parse_env_file(env_file)
        assert result == {"FOO": "bar", "BAZ": "123"}

    def test_strips_quotes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('FOO="bar"\nBAZ=\'qux\'')
        result = parse_env_file(env_file)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_skips_comments_and_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\nFOO=bar\n\nBAZ=123")
        result = parse_env_file(env_file)
        assert result == {"FOO": "bar", "BAZ": "123"}

    def test_invalid_syntax_raises(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("INVALID_LINE")
        with pytest.raises(Exception):
            parse_env_file(env_file)


class TestLoadSchema:
    def test_loads_yaml(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("FOO:\n  required: true\n  type: string")
        result = load_schema(schema_file)
        assert result == {"FOO": {"required": True, "type": "string"}}

    def test_empty_file_returns_empty_dict(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("")
        result = load_schema(schema_file)
        assert result == {}


class TestValidateType:
    def test_string_always_valid(self):
        assert validate_type("anything", "string") is True

    def test_int_valid(self):
        assert validate_type("123", "int") is True
        assert validate_type("-456", "int") is True

    def test_int_invalid(self):
        assert validate_type("abc", "int") is False
        assert validate_type("12.34", "int") is False

    def test_bool_valid(self):
        for val in ["true", "false", "True", "False", "1", "0", "yes", "no"]:
            assert validate_type(val, "bool") is True

    def test_bool_invalid(self):
        assert validate_type("notabool", "bool") is False

    def test_unknown_type_passes(self):
        assert validate_type("anything", "unknown") is True


class TestValidateEnv:
    def test_missing_required(self):
        errors = validate_env({}, {"FOO": {"required": True}})
        assert len(errors) == 1
        assert "Missing required variable: FOO" in errors[0]

    def test_missing_optional_ok(self):
        errors = validate_env({}, {"FOO": {"required": False}})
        assert errors == []

    def test_type_mismatch(self):
        errors = validate_env({"PORT": "abc"}, {"PORT": {"type": "int"}})
        assert len(errors) == 1
        assert "expected int" in errors[0]

    def test_valid_passes(self):
        env = {"DB_URL": "postgres://localhost", "PORT": "5432"}
        schema = {
            "DB_URL": {"required": True, "type": "string"},
            "PORT": {"required": True, "type": "int"},
        }
        errors = validate_env(env, schema)
        assert errors == []


class TestCheckCommand:
    def test_valid_env_passes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar")
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("FOO:\n  required: true")

        result = runner.invoke(app, [str(env_file), "--schema", str(schema_file)])
        assert result.exit_code == 0
        assert "passed" in result.stdout

    def test_missing_required_fails(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("")
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("FOO:\n  required: true")

        result = runner.invoke(app, [str(env_file), "--schema", str(schema_file)])
        assert result.exit_code == 1
        assert "Missing required variable: FOO" in result.stdout

    def test_missing_env_file(self, tmp_path):
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("FOO:\n  required: true")

        result = runner.invoke(app, ["/nonexistent/.env", "--schema", str(schema_file)])
        assert result.exit_code == 1

    def test_missing_schema_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("FOO=bar")

        result = runner.invoke(app, [str(env_file), "--schema", "/nonexistent/schema.yaml"])
        assert result.exit_code == 1
