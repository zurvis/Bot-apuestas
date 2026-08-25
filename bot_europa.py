import time
import sqlite3
import requests
from datetime import datetime

ODDS_API_KEY = "35d963b2ed90438afd3ce1b3d317fa62"
TELEGRAM_TOKEN = "8596607582:AAE5Ca0DIIqvNHhAgPtOb1_2EhedceFWJzk"
TELEGRAM_CHAT_ID = "524615075"

UMBRAL_CAIDA = 0.10          
CUOTA_MINIMA_G_ALTAS = 2.10  

LIGAS_EUROPEAS = {
    "soccer_spain_la_liga": {"name": "La Liga (Espana)", "tarjetas_promedio": 4.8},
    "soccer_italy_serie_a": {"name": "Serie A (Italia)", "tarjetas_promedio": 4.5},
    "soccer_portugal_primeira_liga": {"name": "Primeira Liga (Portugal)", "tarjetas_promedio": 5.2},
    "soccer_epl": {"name": "Premier League (Inglaterra)", "tarjetas_promedio": 3.6},
    "soccer_germany_bundesliga": {"name": "Bundesliga (Alemania)", "tarjetas_promedio": 3.9},
    "soccer_france_ligue_one": {"name": "Ligue 1 (Francia)", "tarjetas_promedio": 4.1},
    "soccer_netherlands_eredivisie": {"name": "Eredivisie (Paises Bajos)", "tarjetas_promedio": 3.2},
    "soccer_uefa_champs_league": {"name": "Champions League", "tarjetas_promedio": 4.0}
}

def inicializar_db():
    conn = sqlite3.connect("cuotas_pro.db")
    conn.cursor().execute('''
        CREATE TABLE IF NOT EXISTS cuotas (
            match_id TEXT, bookmaker TEXT, market TEXT, outcome TEXT, cuota REAL, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (match_id, bookmaker, market, outcome)
        )
    ''')
    conn.commit()
    conn.close()

def enviar_telegram(msg):
    url = f"https://telegram.org{TELEGRAM_TOKEN}/sendMessage"
    try: 
        res = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=12)
        if res.status_code == 200:
            print("=== Mensaje enviado correctamente ===")
    except: 
        print("=== Error de red ===")

def obtener_datos(liga_id):
    url = f"https://the-odds-api.com{liga_id}/odds/"
    params = {"apiKey": ODDS_API_KEY, "regions": "eu", "markets": "totals", "oddsFormat": "decimal"}
    try:
        res = requests.get(url, params=params, timeout=15)
        return res.json() if res.status_code == 200 else []
    except: 
        return []

def calcular_tarjetas(promedio_liga, cuota):
    b = (promedio_liga / 6.5) * 100
    if cuota < 1.60: b += 8.5
    elif cuota > 2.20: b -= 5.0
    return min(max(b, 10.0), 99.0)

def procesar():
    conn = sqlite3.connect("cuotas_pro.db")
    cursor = conn.cursor()
    for liga_key, liga_info in LIGAS_EUROPEAS.items():
        partidos = obtener_datos(liga_key)
        if not isinstance(partidos, list): continue
        for p in partidos:
            match_id = p.get("id")
            home = p.get("home_team")
            away = p.get("away_team")
            for b in p.get("bookmakers", []):
                b_name = b["title"]
                for m in b.get("markets", []):
                    if m["key"] != "totals": continue
                    for o in m.get("outcomes", []):
                        if o.get("name") == "Over" and o.get("point") == 2.5:
                            nc = float(o["price"])
                            if nc >= CUOTA_MINIMA_G_ALTAS:
                                cursor.execute("SELECT cuota FROM cuotas WHERE match_id=? AND bookmaker=? AND outcome=?", (match_id, b_name, "Over 2.5"))
                                row = cursor.fetchone()
                                if row:
                                    cuota_ant = float(row)
                                    if cuota_ant > nc:
                                        caida = (cuota_ant - nc) / cuota_ant
                                        if caida >= UMBRAL_CAIDA:
                                            pt = calcular_tarjetas(liga_info["tarjetas_promedio"], nc)
                                            mensaje = (
                                                f"💣 *ALERTA: MAS DE 2.5 GOLES (CUOTA ALTA)* 💣\n\n"
                                                f"🏆 *Liga:* {liga_info['name']}\n"
                                                f"⚽ *Partido:* {home} vs {away}\n"
                                                f"🏪 *Casa:* {b_name}\n\n"
                                                f"📉 *Caida:* -{caida*100:.1f}%\n"
                                                f"💰 *Antes:* `{cuota_ant:.2f}` -> *Ahora:* `{nc:.2f}`\n"
                                                f"🟨 *Probabilidad de Tarjetas:* {pt:.1f}%"
                                            )
                                            enviar_telegram(mensaje)
                                cursor.execute("INSERT OR REPLACE INTO cuotas VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", (match_id, b_name, "totals", "Over 2.5", nc))
    conn.commit()
    conn.close()

if __name__ == "__main__":
    inicializar_db()
    enviar_telegram("🔄 *Escaneo de Cuotas Altas y Tarjetas en marcha...*")
    procesar()
    print("Escaneo finalizado correctamente.")
