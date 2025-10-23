import discord
import requests
import json
import os
import datetime
import re
import unicodedata
import ast  # ← リスト形式の環境変数を扱うため
import random
import asyncio
import aiohttp

# === 環境変数 ===
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
TARGET_DISCORD_CHANNEL_ID = os.getenv("TARGET_DISCORD_CHANNEL_ID")


# === 検索キーワード読込 ===
def load_keywords():
    raw = os.getenv("SEARCH_KEYWORDS", "")
    if not raw.strip():
        return []
    try:
        # Pythonリスト or JSONリスト形式対応
        parsed = ast.literal_eval(raw)
        if isinstance(parsed, list):
            return [str(s).strip() for s in parsed if str(s).strip()]
    except Exception:
        pass
    # フォールバック: カンマ区切り対応
    return [s.strip() for s in raw.split(",") if s.strip()]


KEYWORDS = load_keywords()


# === チャンネルID設定 ===
if TARGET_DISCORD_CHANNEL_ID:
    TARGET_DISCORD_CHANNEL_ID = int(TARGET_DISCORD_CHANNEL_ID)
else:
    TARGET_DISCORD_CHANNEL_ID = None


# === Discord設定 ===
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# === ログ関数 ===
def log(message, level="INFO"):
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {message}", flush=True)


# === 正規化関数 ===
def normalize_text(s):
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    # スペースを削除ではなく1個に統一
    s = re.sub(r"[\u3000\u200b-\u200d\ufeff]", " ", s)  # 全角空白→半角空白
    s = re.sub(r"\s+", " ", s).strip()  # 余分な空白をまとめる
    return s


# === 転送フィルタ ===
def should_forward(message_content, embeds) -> bool:
    if not KEYWORDS:
        return True

    haystack_parts = []
    if message_content:
        haystack_parts.append(message_content)
    for e in embeds or []:
        for attr in ("title", "description"):
            v = getattr(e, attr, None)
            if v:
                haystack_parts.append(v)
        if getattr(e, "author", None) and getattr(e.author, "name", None):
            haystack_parts.append(e.author.name)

    haystack_raw = "\n".join(haystack_parts)
    haystack_norm = normalize_text(haystack_raw)
    haystack_no_space = haystack_norm.replace(" ", "")

    for kw in KEYWORDS:
        kw_norm = normalize_text(kw)
        kw_no_space = kw_norm.replace(" ", "")

        if (kw_norm in haystack_norm) or (kw_no_space in haystack_no_space):
            log(f"🔥 ヒット: {kw}")
            return True

    log(f"❌ ヒットなし: {KEYWORDS}")
    return False


# === Slack転送 ===
async def send_to_slack(message_content, author_name, embeds, attachments):

    author_name = author_name.replace("• TweetShift#0000", "").strip()

    # --- 現在時刻（JST） ---
    jst = datetime.timezone(datetime.timedelta(hours=9))
    event_time_jst = datetime.datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S JST")

    preview_text = message_content[:80] if message_content else "(メディア投稿)"

    # --- 埋め込みの本文まとめ ---
    embed_texts = []
    embed_url = None

    for embed in embeds or []:
        if embed.title:
            embed_texts.append(f"*{embed.title}*")
        if embed.description:
            embed_texts.append(embed.description)
        if embed.url:
            embed_url = embed.url  # フォールバック用に保存

    embed_text = "\n".join(embed_texts) if embed_texts else "（本文なし）"

    # --- 添付ファイルリスト ---
    if attachments:
        att_list = "\n".join([f"• <{a.url}|{a.filename}>" for a in attachments])
    else:
        att_list = "なし"

    # --- カラーリストからランダム選択 ---
    colors = [
        "#3374ff",  # 青
        "#FF0000",  # 赤
        "#FFFF00",  # 黄
        "#0bff4a",  # 緑
        "#e00bff",  # 紫
        "#ff0b4e",  # ピンク
        "#0bf3ff",  # 水色
        "#ff7a0b"   # オレンジ
    ]
    random_color = random.choice(colors)

    # --- Slackメッセージ本文ブロック ---
    blocks = [
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"✅ *{author_name}*"
                }
            ]
        },
        # {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{preview_text}\n\n{embed_text}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🕒 {event_time_jst}"
                }
            ]
        }
    ]

    # --- アタッチメントカラー付きで送信（ランダムカラー） ---
    attachments_payload = [
        {
            "color": random_color,
            "blocks": blocks
        }
    ]

    # --- Slack送信用データ ---
    slack_data = {
        "text": f"*{author_name}*",
        "blocks": [{"type": "divider"}],
        "attachments": attachments_payload
    }

    # --- Slack送信 ---
    try:
        res = requests.post(
            SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(slack_data)
        )
        if res.status_code == 200:
            log(f"Slackへメッセージを転送しました。✅ (color={random_color})")
        else:
            log(f"Slack送信失敗: {res.status_code} {res.text}", level="ERROR")
    except Exception as e:
        log(f"Slack送信中エラー: {e}", level="ERROR")

# === Discordイベント ===
@client.event
async def on_ready():
    log(f"ログインしました: {client.user}")
    if TARGET_DISCORD_CHANNEL_ID:
        log(f"🎯 監視チャンネルID: {TARGET_DISCORD_CHANNEL_ID}")
    else:
        log("⚠️ チャンネル未指定: 全チャンネル監視モード")
    if KEYWORDS:
        log(f"🔍 検索キーワード: {', '.join(KEYWORDS)}")
    else:
        log("🔍 検索キーワード未設定（全件転送モード）")


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if TARGET_DISCORD_CHANNEL_ID and message.channel.id != TARGET_DISCORD_CHANNEL_ID:
        return
    if not (message.content or message.embeds or message.attachments):
        return

    # 🔁 埋め込みが空なら再取得（Bot投稿などでよくある）
    if message.embeds:
        try:
            msg = await message.channel.fetch_message(message.id)
            message.embeds = msg.embeds
        except Exception as e:
            log(f"⚠️ 埋め込み再取得失敗: {e}")

    # 🔍 フィルタ判定
    if not should_forward(message.content, message.embeds):
        log(f"⏭️ スキップ: {message.author} @ {message.channel}")
        return

    # 🧾 「Tweeted」を含まないメッセージはスキップ
    if message.content:
        first_line = message.content.splitlines()[0]
        if "Tweeted" not in first_line:
            log(f"🚫 Tweetedを含まないためスキップ: {first_line}")
            return

    # ✅ 条件を満たしたらSlack送信
    log(f"📨 転送対象: {message.author} @ {message.channel}: {message.content[:50]}")
    # 非同期でSlackに送る
    asyncio.create_task(
        send_to_slack(message.content, str(message.author), message.embeds, message.attachments)
    )


# === 実行 ===
if not DISCORD_BOT_TOKEN:
    log("❌ DISCORD_BOT_TOKEN が設定されていません。", level="ERROR")
elif not SLACK_WEBHOOK_URL:
    log("❌ SLACK_WEBHOOK_URL が設定されていません。", level="ERROR")
else:
    log("🚀 Discord → Slack転送Bot 起動中...")
    client.run(DISCORD_BOT_TOKEN)
