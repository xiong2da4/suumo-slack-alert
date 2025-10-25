import requests
from bs4 import BeautifulSoup
import time
import csv
import os
from slack_sdk.webhook import WebhookClient

# --------------------------
# 設定
# --------------------------
base_url = 'https://suumo.jp/chintai/hyogo/ek_10110/nj_207/'
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
rn = 2080
page = 1
csv_file = "properties.csv"

# 環境変数からSlack Webhook URLを取得
slack_webhook_url = os.getenv("SLACK_WEBHOOK_URL")
if not slack_webhook_url:
    raise ValueError("Slack Webhook URL が設定されていません。環境変数 SLACK_WEBHOOK_URL を確認してください。")

# --------------------------
# 既存CSV読み込み
# --------------------------
existing_ids = set()
if os.path.exists(csv_file):
    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing_ids.add(row["id"])

all_properties = []

# --------------------------
# ページ取得ループ
# --------------------------
while True:
    if page == 1:
        url = f'{base_url}?rn={rn}'
    else:
        url = f'{base_url}?page={page}&rn={rn}'

    print(f"=== ページ {page} ===")
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    properties = soup.find_all('div', class_='cassetteitem')

    if not properties:
        print("物件が見つからなかったため終了")
        break

    for prop in properties:
        title_tag = prop.find('div', class_='cassetteitem_content-title')
        title = title_tag.get_text(strip=True) if title_tag else "情報なし"

        address_tag = prop.find('li', class_='cassetteitem_detail-col1')
        address = address_tag.get_text(strip=True) if address_tag else "情報なし"

        rooms_data = []
        rooms = prop.find_all('tr', class_='js-cassette_link')
        for room in rooms:
            room_id = room.find('input', class_='js-clipkey')['value']  # 一意ID

            rent_tag = room.find('span', class_='cassetteitem_price--rent')
            rent = rent_tag.get_text(strip=True) if rent_tag else "-"

            fee_tag = room.find('span', class_='cassetteitem_price--administration')
            fee = fee_tag.get_text(strip=True) if fee_tag else "-"

            layout_tag = room.find('span', class_='cassetteitem_madori')
            layout = layout_tag.get_text(strip=True) if layout_tag else "-"

            area_tag = room.find('span', class_='cassetteitem_menseki')
            area = area_tag.get_text(strip=True) if area_tag else "-"

            url_tag = room.find('a', class_='js-cassette_link_href')
            room_url = url_tag['href'] if url_tag else "-"

            rooms_data.append({
                "id": room_id,
                "rent": rent,
                "fee": fee,
                "layout": layout,
                "area": area,
                "url": room_url
            })

        all_properties.append({
            "title": title,
            "address": address,
            "rooms": rooms_data
        })

    page += 1
    time.sleep(1)

# --------------------------
# 新着物件抽出
# --------------------------
new_properties = []
for prop in all_properties:
    new_rooms = [r for r in prop['rooms'] if r['id'] not in existing_ids]
    if new_rooms:
        new_properties.append({
            "title": prop['title'],
            "address": prop['address'],
            "rooms": new_rooms
        })

# --------------------------
# CSVに追記
# --------------------------
with open(csv_file, 'a', newline="", encoding="utf-8") as f:
    fieldnames = ["id", "title", "address", "rent", "fee", "layout", "area", "url"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    if os.path.getsize(csv_file) == 0:
        writer.writeheader()

    for prop in new_properties:
        for room in prop['rooms']:
            writer.writerow({
                "id": room['id'],
                "title": prop['title'],
                "address": prop['address'],
                "rent": room['rent'],
                "fee": room['fee'],
                "layout": room['layout'],
                "area": room['area'],
                "url": room['url']
            })

# --------------------------
# Slack通知（部屋単位で送信）
# --------------------------
BASE_URL = "https://suumo.jp"
webhook = WebhookClient(slack_webhook_url)

total_new_rooms = sum(len(prop['rooms']) for prop in new_properties)
if new_properties:
    for prop in new_properties:
        for room in prop['rooms']:
            message = (
                f"🎉 *新着物件情報* 🎉\n"
                f"🏡 {prop['title']}  📍 {prop['address']}\n"
                f"{room['rent']} / {room['fee']} - {room['layout']} / {room['area']}\n"
                f"🔗 <{BASE_URL}{room['url']}|詳細>\n"
                f"―" * 30
            )
            webhook.send(text=message)
else:
    webhook.send(text="ℹ️ 本日、新着物件はありませんでした 😊")

print(f"Slack通知完了: {total_new_rooms} 件")
