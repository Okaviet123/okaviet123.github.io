#!/usr/bin/env python3
"""蒲郡市 公共施設・財政関連の公開PDFを取得し、LOG/に出典台帳を残す。

`SKILLS/muni-facility-report/scripts/collect_pdfs.py`（汎用テンプレート）を
蒲郡市向けに書き換えたもの。

- レートリミット: 1リクエスト2秒間隔（ガードレール準拠）
- 再実行時は取得済みファイル（同名・非ゼロサイズ）をスキップする
- 台帳: LOG/download_ledger.csv （取得日時UTC, URL, 保存先, バイト数, SHA256）

前提: この環境のネットワークポリシーで www.city.gamagori.lg.jp への
アクセスが許可されていること（2026-07-27時点、未許可。CLAUDE.md参照）。
実行前に1URLへの疎通確認を行うこと（ガードレール必須事項）。

TARGETSのうち決算カード（kessancard/）は、財政状況資料集ページ
(https://www.city.gamagori.lg.jp/unit/zaimu/zaiseijyokyoshiryosyu.html)
内のリンクをネットワーク解禁後に開いて実URLを列挙してから埋めること
（現時点ではファイル名規則が未確認のため空にしてある）。
"""
import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.city.gamagori.lg.jp"
ROOT = Path(__file__).parent
LEDGER = ROOT / "LOG" / "download_ledger.csv"
UA = "gamagori-public-info-report/0.1 (personal civic research; contact: jh8dhv@gmail.com)"
WAIT_SEC = 2.0

# (URL path, 保存先RAW/相対パス, ラベル) — S1偵察(2026-07-27, WebSearch経由)で確定した分のみ記載
TARGETS = [
    # --- 公共施設等総合管理計画（平成29年3月, 令和4年3月一部改訂） ---
    ("/uploaded/attachment/84078.pdf",
     "keikaku/sougou_kanri_keikaku_h29_r4kaitei.pdf", "公共施設等総合管理計画(H29.3, R4.3一部改訂)"),
    # --- 公共施設白書（令和2年度改訂版, 令和3年3月） ---
    ("/uploaded/attachment/74398.pdf",
     "hakusho/hakusho_r2kaitei.pdf", "公共施設白書 令和2年度改訂版"),
    # --- 参考: 将来の人口の見通し ---
    ("/uploaded/attachment/56861.pdf",
     "jinko/shourai_no_jinko_no_mitooshi.pdf", "将来の人口の見通し"),
    # --- 参考: まち・ひと・しごと創生総合戦略2025-2030(案) ---
    ("/uploaded/attachment/106454.pdf",
     "jinko/sougou_senryaku_2025-2030_an.pdf", "まち・ひと・しごと創生総合戦略2025-2030(案)"),
    # --- TODO(S2): 決算カード（財政状況資料集ページ内のリンクをネットワーク解禁後に列挙） ---
    # ("/uploaded/attachment/XXXXX.pdf", "kessancard/kessancard_R05.pdf", "決算カード R05年度"),
    # --- TODO(S2): 公共施設マネジメント基本方針・実施計画の直リンクPDF（未確認） ---
    # ("/uploaded/attachment/XXXXX.pdf", "keikaku/kihon_hoshin_h28.pdf", "公共施設マネジメント基本方針(H28.3)"),
]


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
            url = BASE + url_path
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
