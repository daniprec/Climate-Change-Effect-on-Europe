import json
from pathlib import Path


def collect(root: Path) -> dict[str, list[dict]]:
    entries: list[dict] = []
    for p in root.glob("**/dataset.json"):
        with open(p, "r", encoding="utf-8") as f:
            meta: dict = json.load(f)
        # Optional: validate required keys here
        entries.append(meta)
    return {"datasets": entries}


def main(root: str = "data/processed"):
    out = Path(root) / "catalog.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(collect(Path(root)), f, ensure_ascii=False, indent=2)
    print(f"[OK] catalog written: {out}")


if __name__ == "__main__":
    main()
