#!/usr/bin/env python3
"""蒲郡市 公共施設・財政関連の公開PDF・Excelを取得し、LOG/に出典台帳を残す。

`SKILLS/muni-facility-report/scripts/collect_pdfs.py`（汎用テンプレート）を
蒲郡市向けに書き換えたもの。財政状況資料集は年度によりPDF/Excel(xlsx)が
混在するため、テンプレートから拡張してxlsxも扱えるようにしている。

- レートリミット: 1リクエスト2秒間隔（ガードレール準拠）
- 再実行時は取得済みファイル（同名・非ゼロサイズ）をスキップする
- 台帳: LOG/download_ledger.csv （取得日時UTC, URL, 保存先, バイト数, SHA256）

前提: この環境のネットワークポリシーで www.city.gamagori.lg.jp への
アクセスが許可されていること（2026-07-27時点、未許可。CLAUDE.md参照）。
実行前に1URLへの疎通確認を行うこと（ガードレール必須事項）。

TARGETSのURLは、ネットワークアクセスが使えない状況でユーザーが
Claude Chrome（ユーザー自身のブラウザ、`SKILLS/muni-facility-report/
references/guardrails.md`のフォールバック手順）で各ページのリンクを
実際に開いて確認したもの（2026-07-27）。まだこのセッション側からの
ダウンロード自体は実行できていない（ネットワークポリシー未許可のため）。
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

# (URL path, 保存先RAW/相対パス, ラベル)
TARGETS = [
    # --- 公共施設等総合管理計画（平成29年3月, 令和4年3月一部改訂） ---
    ("/uploaded/attachment/84078.pdf",
     "keikaku/sougou_kanri_keikaku_h29_r4kaitei.pdf", "公共施設等総合管理計画(H29.3, R4.3一部改訂)"),
    # --- 公共施設マネジメント基本方針・実施計画 ---
    ("/uploaded/attachment/34177.pdf",
     "keikaku/kihon_hoshin_h28.pdf", "公共施設マネジメント基本方針(H28.3)"),
    ("/uploaded/attachment/41055.pdf",
     "keikaku/jisshi_keikaku_honpen.pdf", "公共施設マネジメント実施計画(本編)"),
    ("/uploaded/attachment/41259.pdf",
     "keikaku/jisshi_keikaku_gaiyou.pdf", "公共施設マネジメント実施計画(概要版)"),
    # --- 公共施設白書（令和2年度改訂版, 令和3年3月） ---
    ("/uploaded/attachment/74398.pdf",
     "hakusho/hakusho_r2kaitei.pdf", "公共施設白書 令和2年度改訂版"),
    # --- 参考: 将来の人口の見通し ---
    ("/uploaded/attachment/56861.pdf",
     "jinko/shourai_no_jinko_no_mitooshi.pdf", "将来の人口の見通し"),
    # --- 参考: まち・ひと・しごと創生総合戦略2025-2030(案) ---
    ("/uploaded/attachment/106454.pdf",
     "jinko/sougou_senryaku_2025-2030_an.pdf", "まち・ひと・しごと創生総合戦略2025-2030(案)"),
    # --- 財政状況資料集(決算カード等)。年度により形式がPDF/Excelで混在 ---
    ("/uploaded/attachment/114870.xlsx", "kessancard/zaisei_R06.xlsx", "財政状況資料集 R06年度"),
    ("/uploaded/attachment/111937.xlsx", "kessancard/zaisei_R05.xlsx", "財政状況資料集 R05年度"),
    ("/uploaded/attachment/99988.xlsx", "kessancard/zaisei_R04.xlsx", "財政状況資料集 R04年度"),
    ("/uploaded/attachment/97487.xlsx", "kessancard/zaisei_R03.xlsx", "財政状況資料集 R03年度"),
    ("/uploaded/attachment/88570.xlsx", "kessancard/zaisei_R02.xlsx", "財政状況資料集 R02年度"),
    ("/uploaded/attachment/81029.xlsx", "kessancard/zaisei_R01.xlsx", "財政状況資料集 R01年度"),
    ("/uploaded/attachment/74371.xlsx", "kessancard/zaisei_H30.xlsx", "財政状況資料集 H30年度"),
    ("/uploaded/attachment/62266.pdf", "kessancard/kessancard_H29.pdf", "決算カード H29年度"),
    ("/uploaded/attachment/64222.pdf", "kessancard/kessancard_H28.pdf", "決算カード H28年度"),
    ("/uploaded/attachment/42705.xlsx", "kessancard/zaisei_H27.xlsx", "財政状況資料集 H27年度"),
    ("/uploaded/attachment/35725.pdf", "kessancard/kessancard_H26.pdf", "決算カード H26年度"),
    ("/uploaded/attachment/30719.pdf", "kessancard/kessancard_H25.pdf", "決算カード H25年度"),
    ("/uploaded/attachment/27758.pdf", "kessancard/kessancard_H24.pdf", "決算カード H24年度"),
    ("/uploaded/attachment/27553.pdf", "kessancard/kessancard_H23.pdf", "決算カード H23年度"),
    ("/uploaded/attachment/8026.pdf", "kessancard/kessancard_H22.pdf", "決算カード H22年度"),
    ("/uploaded/attachment/2023.pdf", "kessancard/kessancard_H21.pdf", "決算カード H21年度"),
    ("/uploaded/attachment/12789.pdf", "kessancard/kessancard_H20.pdf", "決算カード H20年度"),
    ("/uploaded/attachment/12790.pdf", "kessancard/kessancard_H19.pdf", "決算カード H19年度"),
    ("/uploaded/attachment/12791.pdf", "kessancard/kessancard_H18.pdf", "決算カード H18年度"),
    # H17年度以前は財政状況資料集ページに掲載なし（Claude Chromeでの確認時点、2026-07-27）
]


def looks_valid(rel: str, data: bytes) -> bool:
    """拡張子に応じた最低限のマジックバイト確認。"""
    if rel.endswith(".pdf"):
        return data.startswith(b"%PDF")
    if rel.endswith(".xlsx"):
        return data.startswith(b"PK\x03\x04")  # xlsxはzip形式
    return True


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
                if not looks_valid(rel, data):
                    raise ValueError(f"想定形式ではない可能性 (先頭バイト: {data[:16]!r})")
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
