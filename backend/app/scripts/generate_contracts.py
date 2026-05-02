import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    source = root / "contracts" / "schemas"
    output = root / "backend" / "app" / "contracts" / "generated"
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for path in source.glob("*.schema.json"):
            target_name = path.name.replace("profile-facts", "profile_facts")
            data = json.loads(path.read_text())
            text = json.dumps(data).replace("profile-facts.schema.json", "profile_facts.schema.json")
            (tmp_path / target_name).write_text(text)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "datamodel_code_generator",
                "--input",
                str(tmp_path),
                "--input-file-type",
                "jsonschema",
                "--output",
                str(output),
                "--output-model-type",
                "pydantic_v2.BaseModel",
            ],
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(result.returncode)

    init_file = output / "__init__.py"
    if not init_file.exists():
        init_file.write_text("")

    shutil.rmtree(output / "__pycache__", ignore_errors=True)


if __name__ == "__main__":
    main()
