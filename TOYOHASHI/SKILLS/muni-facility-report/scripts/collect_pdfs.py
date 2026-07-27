#!/usr/bin/env python3
"""汎用PDF収集スクリプト（テンプレート）。

新しい市で使うときは、TARGETS と BASE_URL だけ書き換える。
中身は「URLからダウンロード→出典台帳(LOG/download_ledger.csv)に記録」の
シンプルな構造。豊橋#1の collect_zaisei.py から一般化したもの。

使い方:
  1. フェーズ1(偵察)で見つけたPDFのURLパスと保存先名を TARGETS に列挙する
  2. python3 collect_pdfs.py を実行する
  3. RAW/ 配下にファイルが並び、LOG/download_ledger.csv に記録が追記される

再実行時は取得済み(同名・非ゼロサイズ)のファイルをスキップするので、
TARGETSに追記して再実行すれば差分だけ取得できる。
"""
import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# ==== ここを市ごとに書き換える ====
BASE_URL = "https://www.example.lg.jp"  # 対象市のドメイン
UA = "muni-facility-report/0.1 (personal civic research; contact: YOUR_EMAIL)"
WAIT_SEC = 2.0  # レートリミット目安: 1req/2s

# (URLパス, RAW/以下の保存先相対パス, ラベル)
TARGETS = [
    # 例:
    # ("/secure/12345/keikaku_honpen.pdf", "keikaku/honpen.pdf", "総合管理計画 全体版"),
    # ("/secure/12345/kessancard_R06.pdf", "kessancard/kessancard_R06.pdf", "決算カード R06年度"),
]
# ==================================

ROOT = Path(__file__).parent
LEDGER = ROOT / "LOG" / "download_ledger.csv"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    if not TARGETS:
        print("TARGETSが空です。フェーズ1で見つけたPDFのURLを追記してから実行してください。")
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    new_ledger = not LEDGER.exists()
    with LEDGER.open("a", newline="", encoding="utf-8") as lf:
        w = csv.writer(lf)
        if new_ledger:
            w.writerow(["fetched_at_utc", "url", "saved_to", "bytes", "sha256", "label"])
        ok = skipped = failed = 0
        for url_path, rel, label in TARGETS:
            dest = ROOT / "RAW" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size > 0:
                skipped += 1
                continue
            url = BASE_URL + url_path
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                if not data.startswith(b"%PDF"):
                    raise ValueError(f"PDFではない可能性 (先頭バイト: {data[:16]!r})")
                dest.write_bytes(data)
                w.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            url, str(dest.relative_to(ROOT)), len(data),
                            sha256_of(dest), label])
                lf.flush()
                ok += 1
                print(f"OK   {label}  ({len(data)//1024}KB)")
            except Exception as e:
                failed += 1
                print(f"FAIL {label}: {e}")
            time.sleep(WAIT_SEC)
    print(f"\ndone: ok={ok} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
