import os
import feedparser
import requests
from datetime import datetime

# Ambil token dari Environment Variables yang disuplai oleh GitHub Secrets
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

feed_url = "https://cointelegraph.com/rss"
feed = feedparser.parse(feed_url)

bullish_keywords = ["surge", "jump", "rally", "gain", "bull", "approve", "high", "inflow", "record", "soar", "rise"]
bearish_keywords = ["drop", "crash", "fall", "plunge", "bear", "ban", "hack", "exploit", "outflow", "sec", "lawsuit", "down"]

translations = {
    "bitcoin": "Bitcoin", "ethereum": "Ethereum", "etf": "ETF", "sec": "SEC (OJK AS)",
    "crypto": "Kripto", "market": "Pasar", "price": "Harga", "surge": "melonjak",
    "drop": "turun tajam", "rally": "menguat", "crash": "anjlok", "approves": "menyetujui"
}

def translate_simple(text):
    words = text.split()
    return " ".join([translations.get(w.lower().strip(",.':;\""), w) for w in words])

report_lines = [
    "📊 <b>LAPORAN SENTIMEN PASAR KRIPTO</b>",
    f"📅 <i>Waktu Pembaruan: {datetime.now().strftime('%d-%m-%Y %H:%M')}</i>",
    "━━━━━━━━━━━━━━━━━━━━━━\n"
]

for entry in feed.entries[:5]:
    title = entry.title
    title_lower = title.lower()

    bull_hits = sum(k in title_lower for k in bullish_keywords)
    bear_hits = sum(k in title_lower for k in bearish_keywords)

    if bull_hits > bear_hits:
        status = "🟢 <b>SENTIMEN: POSITIF (BULLISH)</b>"
    elif bear_hits > bull_hits:
        status = "🔴 <b>SENTIMEN: NEGATIF (BEARISH)</b>"
    else:
        status = "⚪ <b>SENTIMEN: NETRAL</b>"

    report_lines.append(
        f"{status}\n"
        f"📰 <b>Judul:</b> {translate_simple(title)}\n"
        f"🔗 <a href='{entry.link}'>Baca Sumber Asli</a>\n"
    )

report_lines.append("━━━━━━━━━━━━━━━━━━━━━━")
report_lines.append("💡 <i>Dikirim otomatis via GitHub Actions</i>")

payload = {
    "chat_id": CHAT_ID,
    "text": "\n".join(report_lines),
    "parse_mode": "HTML",
    "disable_web_page_preview": True
}

resp = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)
print("Status pengiriman:", resp.status_code)
