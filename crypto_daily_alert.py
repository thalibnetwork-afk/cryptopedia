import os
import json
import html
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
    raise ValueError("Variabel environment TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, atau GEMINI_API_KEY belum disetel.")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 2. Ambil Harga Live & Perubahan 24 Jam dari CoinGecko
raw_market_prices = {}

def get_crypto_prices():
    global raw_market_prices
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,solana",
            "vs_currencies": "usd",
            "include_24hr_change": "true"
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            raw_market_prices = res.json()
            
            def format_coin(name, ticker):
                price = raw_market_prices[name]["usd"]
                change = raw_market_prices[name]["usd_24h_change"]
                icon = "🟢" if change >= 0 else "🔴"
                return f"• <b>{ticker}:</b> ${price:,.2f} ({icon} {change:+.2f}%)"

            btc_str = format_coin("bitcoin", "BTC")
            eth_str = format_coin("ethereum", "ETH")
            sol_str = format_coin("solana", "SOL")
            
            return f"{btc_str}\n{eth_str}\n{sol_str}"
    except Exception as e:
        print("Gagal mengambil data harga CoinGecko:", e)
    return "• Data harga pasar sedang tidak tersedia"

# 3. Ambil Data Resmi Crypto Fear & Greed Index
raw_fng_value = 50

def get_fear_and_greed():
    global raw_fng_value
    try:
        res = requests.get("https://api.alternative.me/fng/?limit=1", timeout=5)
        if res.status_code == 200:
            data = res.json()["data"][0]
            val = int(data["value"])
            raw_fng_value = val

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

prices_header = get_crypto_prices()
fng_status = get_fear_and_greed()

# 4. Ambil 20 Berita Terbaru dari RSS Feed
feed_url = "https://cointelegraph.com/rss"
feed = feedparser.parse(feed_url)
raw_articles = []

for entry in feed.entries[:20]:
    raw_articles.append({
        "title": entry.title,
        "summary": entry.get("summary", "")[:250],
        "link": entry.link
    })

# 5. Analisis Cerdas Menggunakan Gemini Pro
system_prompt = """
Anda adalah Senior Crypto Quantitative & Sentiment Analyst berbahasa Indonesia.
Tugas Anda:
1. Analisis 20 artikel berita, momentum harga 24 jam, dan Fear & Greed Index yang diberikan.
2. Tentukan sentimen pasar secara keseluruhan: BULLISH, BEARISH, atau NETRAL.
3. Tulis sintesis kondisi pasar 2-3 kalimat tajam berbahasa Indonesia.
4. Pilih 3 berita PALING berdampak (Top Movers). Terjemahkan judulnya dan berikan alasan dampaknya dalam bahasa Indonesia.
5. Susun Radar Probabilitas:
   - Identifikasi koin yang berkecenderungan MENGUAT (bias naik) beserta alasannya.
   - Identifikasi koin yang berkecenderungan WASPADA KOREKSI (bias turun) beserta alasannya.

KEMBALIKAN HANYA FORMAT JSON VALID:
{
  "overall_bias": "BULLISH / BEARISH / NETRAL",
  "macro_synthesis": "Teks sintesis kondisi pasar",
  "top_market_movers": [
    {
      "title_id": "Judul berita bahasa Indonesia",
      "sentiment": "BULLISH / BEARISH / NETRAL",
      "impact_reason": "Alasan dampak",
      "link": "url"
    }
  ],
  "asset_radar": {
    "bullish_bias": [
      {
        "coin": "BTC",
        "reason": "Alasan bias naik"
      }
    ],
    "bearish_bias": [
      {
        "coin": "ETH",
        "reason": "Alasan bias turun"
      }
    ]
  }
}
"""

payload_prompt = f"""
Data Konteks:
- Momentum Harga 24h: {json.dumps(raw_market_prices)}
- Fear & Greed Index: {raw_fng_value}/100
- 20 Berita Terkini:
{json.dumps(raw_articles, indent=2)}
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

try:
    analysis = json.loads(response.text)
except Exception as e:
    print("Gagal parse JSON LLM:", e)
    analysis = {}

# 6. Susun Pesan Telegram
def safe_html(text: str) -> str:
    return html.escape(str(text)) if text else ""

bias_raw = analysis.get("overall_bias", "NETRAL").upper()
bias_badge = {
    "BULLISH": "🟢 BULLISH",
    "BEARISH": "🔴 BEARISH",
    "NETRAL": "⚪ NETRAL"
}.get(bias_raw, "⚪ NETRAL")

macro_text = safe_html(analysis.get("macro_synthesis", "Analisis pasar sedang diperbarui."))

lines = [
    "🧠 <b>GEMINI PRO: CRYPTO INTELLIGENCE</b>",
    f"📅 <i>Pembaruan: {datetime.now().strftime('%d-%m-%Y %H:%M')} WIB</i>",
    "━━━━━━━━━━━━━━━━━━━━━━",
    "💵 <b>HARGA PASAR (24H):</b>",
    prices_header,
    "━━━━━━━━━━━━━━━━━━━━━━",
    f"🎭 <b>Fear & Greed Index:</b> <code>{fng_status}</code>",
    f"📊 <b>Sentimen Pasar:</b> {bias_badge}",
    "━━━━━━━━━━━━━━━━━━━━━━\n",
    "📌 <b>Rangkuman Eksekutif:</b>",
    f"<i>{macro_text}</i>\n",
    "🎯 <b>RADAR PROBABILITAS KOIN:</b>"
]

radar = analysis.get("asset_radar", {})
bull_list = radar.get("bullish_bias", [])
bear_list = radar.get("bearish_bias", [])

if bull_list:
    lines.append("🟢 <b>Kecenderungan Menguat (Bias Naik):</b>")
    for item in bull_list:
        lines.append(f"• <b>{safe_html(item.get('coin'))}:</b> {safe_html(item.get('reason'))}")
    lines.append("")

if bear_list:
    lines.append("🔴 <b>Waspada Koreksi (Bias Turun):</b>")
    for item in bear_list:
        lines.append(f"• <b>{safe_html(item.get('coin'))}:</b> {safe_html(item.get('reason'))}")
    lines.append("")

lines.append("🔥 <b>Faktor Penggerak Pasar (Top Movers):</b>")
for idx, item in enumerate(analysis.get("top_market_movers", [])[:3], 1):
    tag = "🟢" if item.get("sentiment") == "BULLISH" else ("🔴" if item.get("sentiment") == "BEARISH" else "⚪")
    title_clean = safe_html(item.get("title_id", "Berita Kripto"))
    reason_clean = safe_html(item.get("impact_reason", ""))
    link_url = item.get("link", "#")
    lines.append(
        f"{idx}. {tag} <b>{title_clean}</b>\n"
        f"   └ <i>{reason_clean}</i>\n"
        f"   └ 🔗 <a href='{link_url}'>Baca Sumber</a>\n"
    )

lines.append("━━━━━━━━━━━━━━━━━━━━━━")
lines.append("⚠️ <i>Disclaimer: Analisis probabilitas berbasis sentimen, bukan saran finansial mutlak.</i>")

# 7. Kirim Notifikasi ke Telegram
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

print("Status Pengiriman Telegram:", resp.status_code)
if resp.status_code != 200:
    print("Telegram Error Response:", resp.text)
