import os
import json
import feedparser
import requests
from datetime import datetime
from google import genai
from google.genai import types

# 1. Kredensial Environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not all([BOT_TOKEN, CHAT_ID, GEMINI_KEY]):
    raise ValueError("Variabel environment belum lengkap.")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 2. Ambil 20 Berita Terbaru dari RSS Feed
feed_url = "https://cointelegraph.com/rss"
feed = feedparser.parse(feed_url)
raw_articles = []

# Tingkatkan kuota menjadi 20 artikel
for entry in feed.entries[:20]:
    raw_articles.append({
        "title": entry.title,
        "summary": entry.get("summary", "")[:250],
        "link": entry.link
    })

# 3. Prompt Khusus untuk Gemini Pro (Analisis Makro & Kurasi)
system_prompt = """
Anda adalah Senior Crypto Research Analyst.
Tugas Anda:
1. Baca dan cerna seluruh 20 berita kripto terkini yang diberikan.
2. Identifikasi narasi makro dan tentukan sentimen pasar secara keseluruhan (BULLISH, BEARISH, atau NETRAL).
3. Buat sintesis singkat kondisi pasar dalam 2-3 kalimat tajam berbahasa Indonesia.
4. Pilih 4 berita PALING berdampak (High Impact Movers) terhadap volatilitas dan tren harga kripto.
5. Terjemahkan judulnya dan jelaskan dampaknya secara padat ke Bahasa Indonesia.

Hasilkan HANYA JSON valid sesuai skema yang diminta tanpa markdown pembuka/penutup.
"""

payload_prompt = f"""
Berikut adalah 20 artikel pasar kripto terbaru:
{json.dumps(raw_articles, indent=2)}

Format JSON yang diharapkan:
{{
  "overall_bias": "BULLISH / BEARISH / NETRAL",
  "macro_synthesis": "Ringkasan analisis pasar 2-3 kalimat berbahasa Indonesia.",
  "top_market_movers": [
    {{
      "title_id": "Judul berita dalam Bahasa Indonesia",
      "sentiment": "BULLISH / BEARISH / NETRAL",
      "impact_reason": "Alasan singkat mengapa berita ini berdampak tinggi",
      "link": "link asli dari data input"
    }}
  ]
}}
"""

# 4. Eksekusi Model Gemini Pro
response = ai_client.models.generate_content(
    model="gemini-2.5-pro",
    contents=payload_prompt,
    config=types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json",
        temperature=0.2,
    ),
)

analysis = json.loads(response.text)

# 5. Format Tampilan Pesan Telegram
bias_badge = {
    "BULLISH": "🟢 BULLISH",
    "BEARISH": "🔴 BEARISH",
    "NETRAL": "⚪ NETRAL"
}.get(analysis.get("overall_bias", "NETRAL"), "⚪ NETRAL")

lines = [
    "🧠 <b>GEMINI PRO: CRYPTO INTELLIGENCE</b>",
    f"📅 <i>Pembaruan: {datetime.now().strftime('%d-%m-%Y %H:%M')} WIB</i>",
    f"📊 <b>Sentimen Pasar: {bias_badge}</b>",
    f"📰 <i>Volume Dianalisis: 20 Berita Terkini</i>",
    "━━━━━━━━━━━━━━━━━━━━━━\n",
    "📌 <b>Rangkuman Eksekutif Pasar:</b>",
    f"<i>{analysis.get('macro_synthesis', '')}</i>\n",
    "🔥 <b>Faktor Penggerak Utama (Top Movers):</b>"
]

for idx, item in enumerate(analysis.get("top_market_movers", []), 1):
    tag = "🟢" if item["sentiment"] == "BULLISH" else ("🔴" if item["sentiment"] == "BEARISH" else "⚪")
    lines.append(
        f"\n{idx}. {tag} <b>{item['title_id']}</b>\n"
        f"   └ <i>{item['impact_reason']}</i>\n"
        f"   └ 🔗 <a href='{item['link']}'>Baca Berita Asli</a>"
    )

lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
lines.append("💡 <i>Sintesis cerdas disaring dari 20 artikel menggunakan Gemini Pro</i>")

# 6. Kirim ke Telegram
resp = requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={
        "chat_id": CHAT_ID,
        "text": "\n".join(lines),
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    },
    timeout=20
)

print("Status Pengiriman:", resp.status_code)
