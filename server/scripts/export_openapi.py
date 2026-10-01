"""Write (or check) contracts/openapi.json.

From server/:  uv run python -m scripts.export_openapi          # write
               uv run python -m scripts.export_openapi --check  # fail if out of date
"""

import json
import sys
from pathlib import Path

from app.protocol.schema_app import build_openapi

OUT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.json"


def render() -> str:
    return json.dumps(build_openapi(), indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    text = render()
    if "--check" in argv:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT} is out of date. Run: uv run python -m scripts.export_openapi")
            return 1
        print("openapi.json is up to date")
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text)
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
