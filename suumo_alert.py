import requests
from bs4 import BeautifulSoup
import json
import os
import re

# SUUMO検索URL（川西能勢口駅・2LDK以上）
SEARCH_URL = "https://suumo.jp/chintai/hyogo/ek_10110/nj_207/"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    )
}
STORED_FILE = "prev_results.json"

def fetch_listings():
    """SUUMOから物件リストを取得"""
    resp = requests.get(SEARCH_URL, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items = []
    for el in soup.select(".cassetteitem"):
        title_el = el.select_one(".cassetteitem_content-title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        link = "https://suumo.jp" + title_el["href"]

        try:
            walk_text = el.select_one(".cassetteitem_detail-text").get_text(strip=True)
            walk_min = int(re.search(r"(\d+)分", walk_text).group(1))
        except Exception:
            walk_min = 99

        layout = el.select_one(".cassetteitem_madori").get_text(strip=True)
        items.append({
            "title": title,
            "link": link,
            "walk_min": walk_min,
            "layout": layout
        })
    return items

def filter_condition(items):
    """徒歩10分以内・2LDK以上を抽出"""
    result = []
    for it in items:
        if it["walk_min"] <= 10 and (
            it["layout"].startswith("2LDK")
            or it["layout"].startswith("3LDK")
            or it["layout"].startswith("4LDK")
        ):
            result.append(it)
    return result

def load_prev():
    try:
        with open(STORED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_now(items):
    with open(STORED_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def detect_new(prev, now):
    prev_links = {p["link"] for p in prev}
    return [it for it in now if it["link"] not in prev_links]

def notify_slack(items):
    """Slack通知"""
    webhook = os.getenv("SLACK_WEBHOOK")
    if not webhook:
        print("❌ SLACK_WEBHOOK not found in environment variables.")
        return

    if not items:
        print("No new listings to notify.")
        return

    text = "*🏠 SUUMO 新着物件情報*\n"
    for it in items:
        text += f"• <{it['link']}|{it['title']}>（徒歩{it['walk_min']}分 / {it['layout']})\n"

    payload = {"text": text}

    try:
        response = requests.post(webhook, json=payload)
        if response.status_code == 200:
            print(f"✅ Slack通知成功: {len(items)}件の新着物件を通知しました。")
        else:
            print(f"❌ Slack通知失敗: ステータスコード {response.status_code}")
            print(f"レスポンス内容: {response.text}")
    except Exception as e:
        print(f"❌ Slack通知中に例外が発生しました: {e}")

def main():
    now = fetch_listings()
    filtered = filter_condition(now)
    prev = load_prev()
    new_items = detect_new(prev, filtered)
    if new_items:
        notify_slack(new_items)
    else:
        print("新着物件はありません。")
    save_now(filtered)

if __name__ == "__main__":
    main()
