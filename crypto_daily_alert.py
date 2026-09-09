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

# 2. Ambil Data Resmi Crypto Fear & Greed Index
def get_fear_and_greed():
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if res.status_code == 200:
            data = res.json()["data"][0]
            val = int(data["value"])
            status = data["value_classification"]

            # Visualisasi badge berdasarkan angka
            if val >= 75:
                badge = f"🔥 Extreme Greed ({val}/100)"
            elif val >= 55:
                badge = f"🟢 Greed ({val}/100)"
            elif val <= 25:
                badge = f"🩸 Extreme Fear ({val}/100)"
            elif val <= 45:
                badge = f"🔴 Fear ({val}/100)"
            else:
                badge = f"⚪ Neutral ({val}/100)"
            return badge
    except Exception as e:
        print("Gagal mengambil Fear & Greed Index:", e)
    return "N/A"

fng_status = get_fear_and_greed()

# 3. Ambil 20 Berita Terbaru dari RSS Feed
feed_url = "https://cointelegraph.com/rss"
feed = feedparser.parse(feed_url)
raw_articles = []

for entry in feed.entries[:20]:
    raw_articles.append({
        "title": entry.title,
        "summary": entry.get("summary", "")[:250],
        "link": entry.link
    })

# 4. Prompt Khusus untuk Gemini Pro
system_prompt = """
Anda adalah Senior Crypto Research Analyst berbahasa Indonesia.
Tugas Anda:
1. Baca dan cerna seluruh 20 berita kripto terkini yang diberikan.
2. Identifikasi sentimen pasar secara keseluruhan (BULLISH, BEARISH, atau NETRAL).
3. Buat sintesis singkat kondisi pasar dalam 2-3 kalimat tajam berbahasa Indonesia.
4. Pilih 4 berita PALING berdampak (Top Movers) terhadap pergerakan aset kripto.
5. Terjemahkan judulnya dan jelaskan alasannya secara padat ke Bahasa Indonesia.

Hasilkan HANYA JSON valid sesuai skema yang diminta tanpa format markdown tambahan.
"""

payload_prompt = f"""
Berikut adalah 20 artikel pasar kripto terbaru:
{json.dumps(raw_articles, indent=2)}

Format JSON yang diharapkan:
{{
  "overall_bias": "BULLISH / BEARISH / NETRAL",
  "macro_synthesis": "Ringkasan analisis kondisi pasar 2-3 kalimat berbahasa Indonesia.",
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

# 5. Susun Format Pesan Telegram
bias_badge = {
    "BULLISH": "🟢 BULLISH",
    "BEARISH": "🔴 BEARISH",
    "NETRAL": "⚪ NETRAL"
}.get(analysis.get("overall_bias", "NETRAL"), "⚪ NETRAL")

lines = [
    "🧠 <b>GEMINI PRO: CRYPTO INTELLIGENCE</b>",
    f"📅 <i>Pembaruan: {datetime.now().strftime('%d-%m-%Y %H:%M')} WIB</i>",
    f"🎭 <b>Fear & Greed Index:</b> <code>{fng_status}</code>",
    f"📊 <b>Sentimen Berita:</b> {bias_badge}",
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
lines.append("💡 <i>Kombinasi analisis 20 berita via Gemini Pro + On-chain Sentiment</i>")

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
