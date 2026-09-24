"""수집한 위키문헌 작품(data/wikisource_works.json)을 Firestore data 컬렉션에 적재한다.

실행 (backend 폴더에서):
    python -m scripts.seed_firestore            # 없는 작품만 추가 (중복은 pageid 로 건너뜀)
    python -m scripts.seed_firestore --reset    # 기존 위키문헌 데이터를 지우고 다시 적재
    python -m scripts.seed_firestore --limit 200
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seed import seed  # noqa: E402
from app.storage import get_store  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="기존 위키문헌 출처 문서 삭제 후 적재")
    parser.add_argument("--limit", type=int, default=None, help="적재할 최대 개수")
    args = parser.parse_args()

    result = seed(get_store(), reset=args.reset, limit=args.limit)
    print(f"[data] 삭제 {result['removed']}건 / 추가 {result['added']}건 / 기존 {result['skipped']}건")
    print(f"[library] 삭제 {result['library_removed']}건 / 추가 {result['library_added']}건 / 기존 {result['library_skipped']}건")


if __name__ == "__main__":
    main()
