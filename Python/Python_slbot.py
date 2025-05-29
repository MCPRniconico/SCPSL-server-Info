import discord
import json
import asyncio
import aiohttp
import os
from discord.ext import tasks
from discord import Status, Activity, ActivityType

# ===============================
# 🔧 設定セクション（ここだけ編集すればOK）
# ===============================

TOKEN = 'TOKEN'
WEBHOOK_URL = 'Webhook'
SCPSL_API_URL = 'https://api.scpslgame.com/serverinfo.php?id=ID&key=Api&players=true'
DISPLAY_PORT = 7777
UPDATE_INTERVAL = 60 # 更新間隔（秒）
DATA_FILE = "message_info.json"

# ===============================
# バージョン情報
# ===============================
ver = "v2.0.2"
release_date = "2024/01/01"
release_type = "release"

# ===============================
# 🚀 Bot 起動コード
# ===============================

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

sent_message_id = None

def load_message_id():
    global sent_message_id
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            sent_message_id = data.get("message_id")
            print(f"[読み込み] 保存されたメッセージID: {sent_message_id}")

def save_message_id(message_id):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"message_id": message_id}, f)
    print(f"[保存] メッセージIDを保存しました: {message_id}")

async def get_server_info():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(SCPSL_API_URL) as response:
                text = await response.text()
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print("[エラー] JSON解析に失敗。レスポンス内容（一部）:")
                    print(text[:500])
                    return None

        print(f"[API応答] {json.dumps(data, indent=2)}")

        if not data.get("Success", False):
            print(f"[API失敗] 成功フラグなし: {data.get('Error', '詳細不明')}")
            return None

        servers = data.get("Servers", [])
        if not servers:
            print("[API警告] サーバーが存在しません")
            return None

        return servers[0].get('Players', '不明')

    except aiohttp.ClientError as e:
        print(f"[通信エラー] {type(e).__name__}: {e}")
    except Exception as e:
        print(f"[未知のエラー] {type(e).__name__}: {e}")
    return None

async def send_or_edit_embed(players):
    global sent_message_id

    players_display = f"現在のプレイヤー数: {players}" if players else "プレイヤー数: 不明"
    embed = discord.Embed(
        title="SCPSL サーバー状態",
        description=players_display,
        color=discord.Color.blue()
    )
    embed.add_field(name="サーバー情報", value=f"ポート: {DISPLAY_PORT}", inline=False)
    embed.set_footer(text="Created by kuyu")

    payload = {"embeds": [embed.to_dict()]}

    async with aiohttp.ClientSession() as session:
        if sent_message_id:
            # 編集
            edit_url = f"{WEBHOOK_URL}/messages/{sent_message_id}"
            try:
                async with session.patch(edit_url, json=payload) as resp:
                    if resp.status in [200, 204]:
                        print("[編集成功] メッセージを更新しました")
                    else:
                        print(f"[編集失敗] ステータス: {resp.status}")
                        sent_message_id = None  # 次回新規送信に切り替える
            except Exception as e:
                print(f"[Webhook編集エラー] {type(e).__name__}: {e}")
        else:
            # 新規送信
            try:
                async with session.post(WEBHOOK_URL + "?wait=true", json=payload) as resp:
                    if resp.status in [200, 204]:
                        data = await resp.json()
                        sent_message_id = data.get("id")
                        save_message_id(sent_message_id)
                        print(f"[送信成功] メッセージ送信完了 ID: {sent_message_id}")
                    else:
                        print(f"[送信失敗] ステータス: {resp.status}")
            except Exception as e:
                print(f"[Webhook送信エラー] {type(e).__name__}: {e}")

@tasks.loop(seconds=UPDATE_INTERVAL)
async def periodic_update():
    print("[更新中] サーバー情報取得...")
    players = await get_server_info()
    if players is not None:
        await send_or_edit_embed(players)
    else:
        print("[更新失敗] サーバー情報が取得できませんでした")

@client.event
async def on_ready():
    print(f"[ログイン成功] Bot名: {client.user}")
    print(f"バージョン: {ver} ({release_type})")
    print(f"リリース日: {release_date}")
    await client.change_presence(
        status=Status.online,
        activity=Activity(type=ActivityType.playing, name="SCPSLサーバー")
    )
    load_message_id()
    periodic_update.start()

client.run(TOKEN)
