import json
import logging
import httpx
import datetime
import pytz

logger = logging.getLogger(__name__)

# TU LLAVE MAESTRA
API_KEY = "578532ec4226f7bcf62b67332d582bd1"
BASE_URL = "https://api.the-odds-api.com/v4/sports"

# Mapeo de ligas para no gastar créditos a lo wey
LIGAS_MAP = {
    "nfl": ["americanfootball_nfl"],
    "wnba": ["basketball_wnba"],
    "mlb": ["baseball_mlb"],
    "fútbol": ["soccer_mexico_ligamx", "soccer_spain_la_liga", "soccer_epl", "soccer_uefa_champs_league"],
    "múltiples ligas": ["baseball_mlb", "soccer_mexico_ligamx", "basketball_wnba", "americanfootball_nfl"]
}

async def obtener_datos_partido(liga: str, partido_solicitado: str) -> dict:
    logger.info(f"Iniciando extracción REAL con cazador de momios en The Odds API para: {liga}")
    liga_limpia = liga.lower().replace("⚽", "").replace("🏈", "").replace("🏀", "").replace("⚾", "").strip()
    
    datos = {
        "liga": liga,
        "partido_analizado": partido_solicitado,
        "datos_encontrados": False,
        "detalles": []
    }

    deportes_a_buscar = []
    for key, sports_list in LIGAS_MAP.items():
        if key in liga_limpia:
            deportes_a_buscar = sports_list
            break
            
    if not deportes_a_buscar:
        deportes_a_buscar = ["baseball_mlb"]

    zona_mx = pytz.timezone('America/Mexico_City')
    ahora = datetime.datetime.now(datetime.timezone.utc)

    partidos_reales = []

    async with httpx.AsyncClient() as client:
        for deporte in deportes_a_buscar:
            url = f"{BASE_URL}/{deporte}/odds/"
            params = {
                "apiKey": API_KEY,
                "regions": "us,eu,uk", 
                "markets": "h2h", 
                "oddsFormat": "decimal",
                "dateFormat": "iso"
            }
            
            try:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    juegos = response.json()
                    
                    for juego in juegos:
                        tiempo_juego = datetime.datetime.fromisoformat(juego['commence_time'].replace('Z', '+00:00'))
                        
                        # FILTRO: Si el juego ya empezó, se ignora
                        if tiempo_juego < ahora:
                            continue 
                            
                        hora_mx = tiempo_juego.astimezone(zona_mx).strftime('%d/%m/%Y %H:%M')
                        
                        # CAZADOR DEL MEJOR MOMIO Y MEJOR CASA DE APUESTAS
                        mejor_momio_local = 0.0
                        casa_local = "N/A"
                        mejor_momio_visitante = 0.0
                        casa_visitante = "N/A"

                        if juego.get('bookmakers'):
                            for bookmaker in juego['bookmakers']:
                                nombre_casa = bookmaker['title']
                                for market in bookmaker['markets']:
                                    if market['key'] == 'h2h':
                                        for outcome in market['outcomes']:
                                            if outcome['name'] == juego['home_team']:
                                                if outcome['price'] > mejor_momio_local:
                                                    mejor_momio_local = outcome['price']
                                                    casa_local = nombre_casa
                                            elif outcome['name'] == juego['away_team']:
                                                if outcome['price'] > mejor_momio_visitante:
                                                    mejor_momio_visitante = outcome['price']
                                                    casa_visitante = nombre_casa

                        if mejor_momio_local > 0:
                            partidos_reales.append({
                                "deporte": deporte,
                                "inicio_hora_mexico": hora_mx,
                                "equipo_local": juego['home_team'],
                                "equipo_visitante": juego['away_team'],
                                "mejor_momio_local": f"{mejor_momio_local} (en {casa_local})",
                                "mejor_momio_visitante": f"{mejor_momio_visitante} (en {casa_visitante})"
                            })
                        
                else:
                    logger.error(f"Error de API The Odds: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"Falla conectando a The Odds API: {e}")

    if partidos_reales:
        datos["datos_encontrados"] = True
        datos["detalles"] = partidos_reales
    
    return datos

def construir_prompt_contexto(datos_partido: dict) -> str:
    if not datos_partido or not datos_partido.get("datos_encontrados"):
        return "[INFORMACIÓN] ALERTA CRÍTICA: No hay partidos programados para el resto de este día o la API no encontró juegos. NO INVENTES NINGÚN PARTIDO. Dile al usuario que la cartelera de hoy ya se terminó o está vacía."

    liga = datos_partido.get("liga", "Liga Desconocida")
    partido = datos_partido.get("partido_analizado", "Partido no especificado")
    detalles = datos_partido.get("detalles", [])

    contexto = f"=== CARTELERA DE PARTIDOS 100% REALES PARA HOY ({liga}) ===\n"
    contexto += f"Petición del usuario: {partido}\n\n"
    contexto += "¡ATENCIÓN! Estos son los únicos partidos reales de hoy con la referencia de momios globales.\n"
    contexto += "INSTRUCCIÓN ESTRICTA PARA LA IA: Cuando des tu pronóstico final, adapta la recomendación para el mercado mexicano. "
    contexto += "Dile al usuario que busque y meta esta apuesta en sus casas favoritas como Caliente Casino, BetVIP, Betxico, Novibet, Draftea o Winpot, "
    contexto += "ya que las líneas serán prácticamente idénticas a la referencia global que te presento abajo:\n\n"
    
    for p in detalles:
        contexto += f"🥊 {p['equipo_local']} vs {p['equipo_visitante']} | ⌚ Empieza: {p['inicio_hora_mexico']} \n"
        contexto += f"💰 Referencia de pago Global -> Local: {p['mejor_momio_local']} | Visitante: {p['mejor_momio_visitante']}\n"
        contexto += "-" * 40 + "\n"
        
    contexto += "\n========================================================"
    return contexto
