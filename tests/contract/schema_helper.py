import json
from pathlib import Path
import jsonschema

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def load_schema(schema_name: str) -> dict:
    if not schema_name.endswith(".json"):
        schema_name = f"{schema_name}.json"
    file_path = SCHEMAS_DIR / schema_name
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_schema(data: dict, schema_name: str):
    schema = load_schema(schema_name)
    resolver = jsonschema.validators.RefResolver(
        base_uri=f"file:///{SCHEMAS_DIR.as_posix()}/",
        referrer=schema
    )
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, resolver=resolver, format_checker=jsonschema.FormatChecker())
    validator.validate(data)
