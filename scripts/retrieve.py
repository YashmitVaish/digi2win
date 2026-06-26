import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.services.retrieve import retrieve
from backend.util.memory import MEMORY_TYPES


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieve top memories for a query.")
    parser.add_argument("query", type=str, help="Query text")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results")
    parser.add_argument(
        "--filter-type",
        type=str,
        choices=sorted(MEMORY_TYPES),
        help="Only return a single memory type",
    )
    args = parser.parse_args()

    results = retrieve(args.query, top_k=args.top_k, filter_type=args.filter_type)
    if not results:
        print("No memories found.")
        return

    for idx, item in enumerate(results, start=1):
        print(f"{idx}. ({item['type']}) score={item['score']:.4f}")
        print(f"   {item['content']}")


if __name__ == "__main__":
    main()
