import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.db.chroma import reset_collection
from backend.db.db import Memory, SessionLocal
from backend.services.ingest import ingest


def reset_vector_and_memory_store() -> None:
    reset_collection()
    db = SessionLocal()
    try:
        db.query(Memory).delete()
        db.commit()
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest text into Twin memory.")
    parser.add_argument("--text", type=str, help="Text to ingest")
    parser.add_argument("--file", type=str, help="Path to text file to ingest")
    parser.add_argument(
        "--type",
        type=str,
        default="auto",
        choices=["auto", "fact", "preference", "event", "goal", "style"],
        help="Memory type",
    )
    parser.add_argument("--importance", type=float, default=1.0, help="Importance score")
    parser.add_argument("--reset-chroma", action="store_true", help="Reset Chroma + memory rows first")
    args = parser.parse_args()

    if not args.text and not args.file:
        raise SystemExit("Provide --text or --file")

    if args.reset_chroma:
        reset_vector_and_memory_store()
        print("Reset Chroma collection and memory table.")

    content = args.text
    if args.file:
        content = Path(args.file).read_text(encoding="utf-8")

    chunks = ingest(content=content or "", memory_type=args.type, importance=args.importance)
    print(f"Ingested {chunks} chunk(s).")


if __name__ == "__main__":
    main()
