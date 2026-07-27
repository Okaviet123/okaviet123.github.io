#!/usr/bin/env python3
"""豊橋市 公共施設・財政関連の公開PDFを取得し、LOG/に出典台帳を残す。

- レートリミット: 1リクエスト2秒間隔（ガードレール準拠）
- 再実行時は取得済みファイル（同名・非ゼロサイズ）をスキップする
- 台帳: LOG/download_ledger.csv （取得日時UTC, URL, 保存先, バイト数, SHA256）
"""
import csv
import hashlib
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "https://www.city.toyohashi.lg.jp"
ROOT = Path(__file__).parent
LEDGER = ROOT / "LOG" / "download_ledger.csv"
UA = "toyohashi-public-info-report/0.1 (personal research; contact: jh8dhv@gmail.com)"
WAIT_SEC = 2.0

# (URL path, 保存先RAW/相対パス, ラベル)
TARGETS = [
    # --- 公共施設等総合管理計画2026-2055（令和8年3月, /64295.htm） ---
    ("/secure/122819/koukyousisetutousougoukannrikeikaku2026-2055.pdf",
     "keikaku2026/sougou_kanri_keikaku_2026-2055_full.pdf", "総合管理計画2026-2055 全体版"),
    ("/secure/122819/koukyousisetutousougoukannrikeikakugaiyoubann2026-2055.pdf",
     "keikaku2026/sougou_kanri_keikaku_2026-2055_gaiyou.pdf", "総合管理計画2026-2055 概要版"),
    # --- 施設最適化計画2026-2035（/64296.htm） ---
    ("/secure/122822/sisetusaitekikakeikaku2026-2035.pdf",
     "keikaku2026/saitekika_keikaku_2026-2035_full.pdf", "施設最適化計画2026-2035 全体版"),
    # --- 施設保全計画2026-2035（/64298.htm） ---
    ("/secure/122827/sisetuhozennkeikaku2026-2035.pdf",
     "keikaku2026/hozen_keikaku_2026-2035_full.pdf", "施設保全計画2026-2035 全体版"),
    # --- 旧: 公共施設等総合管理方針（平成29年3月, /18185.htm）比較用 ---
    ("/secure/48223/sogokanrihoshin_toyohashi.pdf",
     "hoshin2017/sougou_kanri_houshin_2017_full.pdf", "総合管理方針(H29.3) 全体版"),
    # --- 公共施設白書2025（/34019.htm） ---
    ("/secure/117134/toyohasisikyoukyousisetuhakusho2025.pdf",
     "hakusho/hakusho2025_full.pdf", "公共施設白書2025 全ページ"),
    ("/secure/117134/kobetuhyoubunnkashakaikyouikukeisisetu.pdf",
     "hakusho/kobetsu_bunka_shakaikyouiku.pdf", "個別票 文化・社会教育系"),
    ("/secure/117134/kobetuhyousupo-tusisetu.pdf",
     "hakusho/kobetsu_sports.pdf", "個別票 スポーツ系"),
    ("/secure/117134/kobetuhyousanngyoukeisisetu.pdf",
     "hakusho/kobetsu_sangyou.pdf", "個別票 産業系"),
    ("/secure/117134/kobetuhyougakkoukyouikukeisisetu.pdf",
     "hakusho/kobetsu_gakkou.pdf", "個別票 学校教育系"),
    ("/secure/117134/kobetuhyoukosodatesisetu.pdf",
     "hakusho/kobetsu_kosodate.pdf", "個別票 子育て系"),
    ("/secure/117134/kobetuhyouiryoufukusikeisisetu.pdf",
     "hakusho/kobetsu_iryou_fukushi.pdf", "個別票 医療・保健福祉系"),
    ("/secure/117134/kobetuhyousonotasisetu.pdf",
     "hakusho/kobetsu_sonota.pdf", "個別票 その他"),
    ("/secure/117134/kobetuhyougyouseikeisisetu.pdf",
     "hakusho/kobetsu_gyousei.pdf", "個別票 行政系"),
    # --- 人口ビジョン ---
    ("/secure/82979/zinkoubizyon.pdf",
     "jinko/jinkou_vision.pdf", "豊橋市人口ビジョン"),
]

# 決算カード 平成14〜令和6年度（/2529.htm）。ファイル名が年度ごとに不規則なので列挙。
KESSAN_CARDS = [
    ("R06kessancard.pdf", "R06"), ("R05kessancard.pdf", "R05"),
    ("R04_kessancard.pdf", "R04"), ("R3kessancard.pdf", "R03"),
    ("R02kessanka-do.pdf", "R02"), ("R01kessanka-do.pdf", "R01"),
    ("30kessancard.pdf", "H30"), ("29kessancard.pdf", "H29"),
    ("28kessancard.pdf", "H28"), ("27kessancard.pdf", "H27"),
    ("26kessancard.pdf", "H26"), ("25kessancard.pdf", "H25"),
    ("24kessancard2.pdf", "H24"), ("23kessancard.pdf", "H23"),
    ("22kessan.pdf", "H22"), ("21kessancard.pdf", "H21"),
    ("20kessancard.pdf", "H20"), ("19kessancard.pdf", "H19"),
    ("18kessancard.pdf", "H18"), ("17kessancard.pdf", "H17"),
    ("16kessancard.pdf", "H16"), ("15kessancard.pdf", "H15"),
    ("14kessancard.pdf", "H14"),
]
for fname, nendo in KESSAN_CARDS:
    TARGETS.append((f"/secure/20033/{fname}",
                    f"kessancard/kessancard_{nendo}.pdf", f"決算カード {nendo}年度"))


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
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
                    raise ValueError(f"not a PDF (first bytes: {data[:16]!r})")
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
