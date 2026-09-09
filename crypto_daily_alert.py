import os
import json
import feedparser
import requests
from datetime import datetime
from google import genai
from google.genai import types

# 1. Inisialisasi Kredensial
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not all([BOT_TOKEN, CHAT_ID, GEMINI_KEY]):
    raise ValueError("Salah satu environment variable (Telegram/Gemini) belum disetel.")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 2. Ambil 5 Berita Terbaru dari RSS Cointelegraph
feed_url = "https://cointelegraph.com/rss"
feed = feedparser.parse(feed_url)
raw_articles = []

for entry in feed.entries[:5]:
    raw_articles.append({
        "title": entry.title,
        "link": entry.link,
        "summary": entry.get("summary", "")[:250]
    })

# 3. Analisis Cerdas Menggunakan Gemini Flash
system_prompt = """
Anda adalah Crypto Market Intelligence Assistant berbahasa Indonesia.
Tugas Anda:
1. Menganalisis daftar berita kripto yang diberikan.
2. Menentukan sentimen pasar untuk setiap berita (BULLISH, BEARISH, atau NETRAL).
3. Menerjemahkan inti berita ke dalam Bahasa Indonesia yang alami dan ringkas (maksimal 2 kalimat per berita).
4. Menyimpulkan keseluruhan bias pasar (BULLISH / BEARISH / NETRAL).

Hasilkan keluaran HANYA dalam format JSON valid tanpa format markdown tambahan.
"""

payload_prompt = f"""
Analisis artikel-artikel kripto berikut:
{json.dumps(raw_articles, indent=2)}

Format JSON yang diharapkan:
{{
  "overall_bias": "BULLISH / BEARISH / NETRAL",
  "articles": [
    {{
      "title_id": "Judul dalam Bahasa Indonesia yang jelas",
      "sentiment": "BULLISH / BEARISH / NETRAL",
      "brief_summary": "Ringkasan 1-2 kalimat kenapa berita ini penting",
      "link": "link asli dari data input"
    }}
  ]
}}
"""

response = ai_client.models.generate_content(
    model="gemini-2.5-flash",
    contents=payload_prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        temperature=0.2,
    ),
)

analysis = json.loads(response.text)

# 4. Susun Format Pesan Telegram
bias_badge = {
    "BULLISH": "🟢 BULLISH",
    "BEARISH": "🔴 BEARISH",
    "NETRAL": "⚪ NETRAL"
}.get(analysis.get("overall_bias", "NETRAL"), "⚪ NETRAL")

lines = [
    "🤖 <b>AI INTELLIGENCE SENTIMENT REPORT</b>",
    f"📅 <i>Pembaruan: {datetime.now().strftime('%d-%m-%Y %H:%M')} WIB</i>",
    f"🎯 <b>Bias Pasar Umum: {bias_badge}</b>",
    "━━━━━━━━━━━━━━━━━━━━━━\n"
]

for item in analysis.get("articles", []):
    s_tag = "🟢" if item["sentiment"] == "BULLISH" else ("🔴" if item["sentiment"] == "BEARISH" else "⚪")
    lines.append(
        f"{s_tag} <b>[{item['sentiment']}]</b>\n"
        f"📰 <b>{item['title_id']}</b>\n"
        f"📝 <i>{item['brief_summary']}</i>\n"
        f"🔗 <a href='{item['link']}'>Sumber Berita</a>\n"
    )

lines.append("━━━━━━━━━━━━━━━━━━━━━━")
lines.append("💡 <i>Dianalisis otomatis oleh Gemini 2.5 Flash & GitHub Actions</i>")

# 5. Kirim Notifikasi ke Telegram
resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    },
    timeout=15
)

print("Status Notifikasi:", resp.status_code)
