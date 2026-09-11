import os
import json
import html
import time
import feedparser
import requests
from datetime import datetime, timezone, timedelta
from google import genai
from google.genai import types

# 1. Kredensial Environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not all([BOT_TOKEN, CHAT_ID, GEMINI_KEY]):
    raise ValueError("Variabel environment belum lengkap.")

ai_client = genai.Client(api_key=GEMINI_KEY)

# 2. Ambil Harga Live Pasar (BTC, ETH, SOL) dengan Bypass Cache
raw_market_prices = {}
def get_crypto_prices():
    global raw_market_prices
    url = f"https://api.coingecko.com/api/v3/simple/price?t={int(time.time())}"
    params = {"ids": "bitcoin,ethereum,solana", "vs_currencies": "usd", "include_24hr_change": "true"}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache"
    }
    try:
        res = requests.get(url, params=params, headers=headers, timeout=10)
        if res.status_code == 200:
            raw_market_prices = res.json()
            def fmt(c, t):
                p = raw_market_prices.get(c, {}).get("usd", 0)
                chg = raw_market_prices.get(c, {}).get("usd_24h_change", 0)
                ic = "🟢" if chg >= 0 else "🔴"
                return f"• <b>{t}:</b> ${p:,.2f} ({ic} {chg:+.2f}%)"
            return f"{fmt('bitcoin', 'BTC')}\n{fmt('ethereum', 'ETH')}\n{fmt('solana', 'SOL')}"
    except Exception as e:
        print("[CoinGecko Price Error]:", e)
    return "• Data harga pasar tidak tersedia"

# 3. Ambil Koin Trending (CoinGecko Trending)
raw_trending_coins = []
def get_trending_coins():
    global raw_trending_coins
    url = f"https://api.coingecko.com/api/v3/search/trending?t={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("coins", [])[:5]
            for it in items:
                coin_data = it.get("item", {})
                raw_trending_coins.append({
                    "name": coin_data.get("name"),
                    "symbol": coin_data.get("symbol"),
                    "market_cap_rank": coin_data.get("market_cap_rank")
                })
    except Exception as e:
        print("[CoinGecko Trending Error]:", e)

# 4. Ambil Fear & Greed Index
raw_fng_value = 50
def get_fear_and_greed():
    global raw_fng_value
    url = f"https://api.alternative.me/fng/?limit=1&t={int(time.time())}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Cache-Control": "no-cache"
    }
    try:
        res = requests.get(url, headers=headers, timeout=5)
        if res.status_code == 200:
            val = int(res.json()["data"][0]["value"])
            raw_fng_value = val
            if val >= 75: return f"🔥 Extreme Greed ({val}/100)"
            if val >= 55: return f"🟢 Greed ({val}/100)"
            if val <= 25: return f"🩸 Extreme Fear ({val}/100)"
            if val <= 45: return f"🔴 Fear ({val}/100)"
            return f"⚪ Neutral ({val}/100)"
    except Exception as e:
        print("[Fear&Greed Error]:", e)
    return "N/A"

prices_header = get_crypto_prices()
get_trending_coins()
fng_status = get_fear_and_greed()

# 5. Tarik Berita Live Terbaru (Anti-Cache & Anti-Delay)
rss_url = f"https://cointelegraph.com/rss?timestamp={int(time.time())}"
headers_rss = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache"
}

raw_articles = []
try:
    rss_res = requests.get(rss_url, headers=headers_rss, timeout=15)
    feed = feedparser.parse(rss_res.text)
    for e in feed.entries[:20]:
        raw_articles.append({
            "title": e.title,
            "summary": e.get("summary", "")[:250],
            "published": e.get("published", ""),
            "link": e.link
        })
except Exception as e:
    print("[RSS Scrape Error]:", e)

# Waktu sekarang dalam zona WITA (UTC+8)
wita_tz = timezone(timedelta(hours=8))
wita_now = datetime.now(wita_tz).strftime('%d-%m-%Y %H:%M')

# 6. Analisis Menggunakan Gemini 3.6 Flash
prompt = f"""
Anda adalah Senior Crypto Quantitative & Sentiment Analyst berbahasa Indonesia.
Waktu saat ini: {wita_now} WITA.

Analisis data pasar teraktual berikut:
- Harga 24h: {json.dumps(raw_market_prices)}
- Fear & Greed Index: {raw_fng_value}/100
- Daftar Koin Trending Populer: {json.dumps(raw_trending_coins)}
- 20 Berita Kripto Terkini (perhatikan waktu published): {json.dumps(raw_articles, indent=2)}

Tugas Anda:
1. Berikan sentimen pasar umum (BULLISH/BEARISH/NETRAL) dan ringkasan eksekutif makro (2-3 kalimat tajam).
2. Susun RADAR PROBABILITAS KOIN UTAMA (bias naik vs waspada koreksi).
3. Analisis KOIN TRENDING (emerging gems):
   - Pilih 2 koin trending yang memiliki katalis/potensi sentimen positif terkuat untuk naik.
   - Jelaskan alasan potensi & narasi hype-nya dalam 1 kalimat padat.
4. Pilih 3 Berita Penggerak Pasar Terkini (Top Movers).

KEMBALIKAN HANYA FORMAT JSON VALID:
{{
  "overall_bias": "BULLISH / BEARISH / NETRAL",
  "macro_synthesis": "Ringkasan analisis pasar berbahasa Indonesia.",
  "asset_radar": {{
    "bullish_bias": [{{"coin": "TICKER", "reason": "alasan menguat"}}],
    "bearish_bias": [{{"coin": "TICKER", "reason": "alasan waspada"}}]
  }},
  "trending_gems": [
    {{
      "coin": "NAMA_KOIN (TICKER)",
      "potential": "Alasan potensi naik berdasarkan sentimen/komunitas"
    }}
  ],
  "top_market_movers": [
    {{"title_id": "Judul bahasa Indonesia", "sentiment": "BULLISH/BEARISH/NETRAL", "impact_reason": "Alasan dampak", "link": "url"}}
  ]
}}
"""

# Eksekusi AI dengan Penanganan Retry (Anti-503)
data = {}
for attempt in range(1, 4):
    try:
        print(f"Mengirim permintaan ke Gemini (Percobaan ke-{attempt})...")
        resp = ai_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        data = json.loads(resp.text)
        print("Analisis AI berhasil diterima.")
        break
    except Exception as e:
        print(f"Percobaan {attempt} gagal ({e}). Menunggu 5 detik...")
        time.sleep(5)

if not data:
    raise RuntimeError("Gagal memproses analisis Gemini setelah 3 percobaan.")

# 7. Susun Format Pesan Telegram
def safe(t): return html.escape(str(t)) if t else ""
bias_raw = data.get("overall_bias", "NETRAL").upper()
bias_badge = {"BULLISH": "🟢 BULLISH", "BEARISH": "🔴 BEARISH"}.get(bias_raw, "⚪ NETRAL")

lines = [
    "🤖 <b>AI INTELLIGENCE: CRYPTO ALERT</b>",
    f"📅 <i>Pembaruan: {wita_now} WITA</i>",
    "━━━━━━━━━━━━━━━━━━━━━━",
    "💵 <b>HARGA PASAR (24H):</b>",
    prices_header,
    "━━━━━━━━━━━━━━━━━━━━━━",
    f"🎭 <b>Fear & Greed:</b> <code>{fng_status}</code>",
    f"📊 <b>Sentimen Pasar:</b> {bias_badge}",
    "━━━━━━━━━━━━━━━━━━━━━━\n",
    "📌 <b>Rangkuman Eksekutif:</b>",
    f"<i>{safe(data.get('macro_synthesis'))}</i>\n",
    "🎯 <b>RADAR PROBABILITAS (Blue Chip):</b>"
]

radar = data.get("asset_radar", {})
for b in radar.get("bullish_bias", []):
    lines.append(f"🟢 <b>{safe(b.get('coin'))}:</b> {safe(b.get('reason'))}")
for b in radar.get("bearish_bias", []):
    lines.append(f"🔴 <b>{safe(b.get('coin'))}:</b> {safe(b.get('reason'))}")

gems = data.get("trending_gems", [])
if gems:
    lines.append("\n💎 <b>RADAR KOIN TRENDING & POTENSIAL (High Risk/Hype):</b>")
    for g in gems:
        lines.append(f"⚡ <b>{safe(g.get('coin'))}:</b> {safe(g.get('potential'))}")

lines.append("\n🔥 <b>Faktor Penggerak Pasar Terkini:</b>")
for idx, it in enumerate(data.get("top_market_movers", [])[:3], 1):
    lines.append(f"{idx}. <b>{safe(it.get('title_id'))}</b>\n   └ <i>{safe(it.get('impact_reason'))}</i>\n   └ 🔗 <a href='{it.get('link')}'>Sumber</a>")

lines.append("\n━━━━━━━━━━━━━━━━━━━━━━\n⚠️ <i>Radar probabilitas berbasis sentimen & momentum, bukan anjuran finansial mutlak.</i>")

telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
res = requests.post(
    telegram_url,
    json={"chat_id": CHAT_ID, "text": "\n".join(lines), "parse_mode": "HTML", "disable_web_page_preview": True},
    timeout=20
)

print(f"Status Pengiriman Telegram: {res.status_code}")
if res.status_code != 200:
    print("Gagal:", res.text)
