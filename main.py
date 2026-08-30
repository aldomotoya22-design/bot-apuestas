import logging
import os
import sys
import threading
import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from data_scraper import obtener_datos_partido, construir_prompt_contexto
from ai_engine import generar_analisis

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- TRUCO PARA RENDER GRATIS ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot activo y al cien")

def keep_alive():
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()
# --------------------------------

def obtener_menu_principal() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🏈 NFL", callback_data="liga_nfl"),
            InlineKeyboardButton("🏀 WNBA", callback_data="liga_wnba"),
        ],
        [
            InlineKeyboardButton("⚾ MLB", callback_data="liga_mlb"),
            InlineKeyboardButton("⚽ Fútbol", callback_data="liga_futbol"),
        ],
        [
            InlineKeyboardButton("🔥 Picks de Alto Valor Hoy", callback_data="picks_valor")
        ],
    ]
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    context.user_data.clear()
    
    welcome_text = (
        f"¡Hola, {user.first_name}! 👋\n\n"
        "Bienvenido al Bot de Análisis Predictivo y Apuestas Deportivas.\n"
        "Selecciona una liga para comenzar el análisis:"
    )

    await update.message.reply_text(
        text=welcome_text, 
        reply_markup=obtener_menu_principal()
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    ligas_map = {
        "liga_nfl": "🏈 NFL",
        "liga_wnba": "🏀 WNBA",
        "liga_mlb": "⚾ MLB",
        "liga_futbol": "⚽ Fútbol",
    }

    data = query.data

    if data in ligas_map:
        nombre_liga = ligas_map[data]
        context.user_data['liga_seleccionada'] = nombre_liga
        
        mensaje_respuesta = (
            f"Has seleccionado *{nombre_liga}*.\n\n"
            "Escribe el partido y el mercado que deseas analizar.\n"
            "_(Ej: Chiefs vs Ravens - Over 45.5)_"
        )
        teclado_volver = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
        ])
        await query.edit_message_text(
            text=mensaje_respuesta, 
            reply_markup=teclado_volver, 
            parse_mode="Markdown"
        )

    # --- SECCIÓN DE PICKS DE VALOR CORREGIDA ---
    elif data == "picks_valor":
        await query.edit_message_text(
            text="🔥 *Buscando Picks de Alto Valor Hoy...*\n⏳ _Extrayendo datos y conectando a los algoritmos cuantitativos..._", 
            parse_mode="Markdown"
        )
        
        try:
            # La IA busca los mejores datos del día
            datos = await obtener_datos_partido("Todas las ligas", "Mejores Picks de Alto Valor Hoy")
            contexto_datos = construir_prompt_contexto(datos)
            
            await query.edit_message_text(
                text="🔥 *Buscando Picks de Alto Valor Hoy...*\n🧠 _Consultando al motor cuantitativo de IA..._",
                parse_mode="Markdown"
            )
            
            # Genera el análisis de alto valor
            analisis_final = await generar_analisis("Todas las ligas", "Mejores Picks de Alto Valor Hoy", contexto_datos)
            
            if "===MEDIO===" in analisis_final and "===ALTO===" in analisis_final:
                partes_medio = analisis_final.split("===MEDIO===")
                context.user_data['pick_oro'] = partes_medio[0].strip()
                
                partes_alto = partes_medio[1].split("===ALTO===")
                context.user_data['pick_medio'] = partes_alto[0].strip()
                context.user_data['pick_alto'] = partes_alto[1].strip()
                
                texto_mostrar = context.user_data['pick_oro']
                botones = [
                    [InlineKeyboardButton("⚖️ Riesgo Medio", callback_data="ver_medio"), 
                     InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")],
                    [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
                ]
                teclado = InlineKeyboardMarkup(botones)
            else:
                texto_mostrar = analisis_final
                teclado = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
                ])
            
            await query.edit_message_text(
                text=texto_mostrar,
                reply_markup=teclado,
                parse_mode=None
            )
            
        except Exception as e:
            logger.error(f"Error en picks de valor: {e}")
            teclado_volver = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
            ])
            await query.edit_message_text(
                text="⚠️ Ocurrió un error al buscar los picks de valor. Intenta de nuevo.",
                reply_markup=teclado_volver
            )
    # -------------------------------------------

    elif data == "volver_menu":
        context.user_data.clear()
        welcome_text = "Selecciona una liga para comenzar el análisis:"
        await query.edit_message_text(
            text=welcome_text, 
            reply_markup=obtener_menu_principal()
        )
        
    elif data.startswith("ver_"):
        if data == "ver_oro":
            texto = context.user_data.get('pick_oro', '⚠️ Pick no encontrado.')
            botones = [
                [InlineKeyboardButton("⚖️ Riesgo Medio", callback_data="ver_medio"), 
                 InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")],
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
            ]
        elif data == "ver_medio":
            texto = context.user_data.get('pick_medio', '⚠️ Pick no encontrado.')
            botones = [
                [InlineKeyboardButton("👑 Pick de Oro", callback_data="ver_oro"), 
                 InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")],
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
            ]
        elif data == "ver_alto":
            texto = context.user_data.get('pick_alto', '⚠️ Pick no encontrado.')
            botones = [
                [InlineKeyboardButton("👑 Pick de Oro", callback_data="ver_oro"), 
                 InlineKeyboardButton("⚖️ Riesgo Medio", callback_data="ver_medio")],
                [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
            ]
        
        await query.edit_message_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(botones),
            parse_mode=None
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    liga = context.user_data.get('liga_seleccionada')
    
    if not liga:
        await update.message.reply_text(
            "⚠️ Por favor, primero selecciona una liga en el menú de /start"
        )
        return
        
    partido_solicitado = update.message.text
    context.user_data['partido'] = partido_solicitado
    
    mensaje_espera = await update.message.reply_text(
        text=f"⚙️ Procesando análisis para la *{liga}*...\n⏳ _Extrayendo datos deportivos..._",
        parse_mode="Markdown"
    )
    
    try:
        datos = await obtener_datos_partido(liga, partido_solicitado)
        contexto_datos = construir_prompt_contexto(datos)
        
        await mensaje_espera.edit_text(
            text=f"⚙️ Procesando análisis para la *{liga}*...\n🧠 _Consultando al motor cuantitativo de IA..._",
            parse_mode="Markdown"
        )
        
        analisis_final = await generar_analisis(liga, partido_solicitado, contexto_datos)
        
        if "===MEDIO===" in analisis_final and "===ALTO===" in analisis_final:
            partes_medio = analisis_final.split("===MEDIO===")
            context.user_data['pick_oro'] = partes_medio[0].strip()
            
            partes_alto = partes_medio[1].split("===ALTO===")
            context.user_data['pick_medio'] = partes_alto[0].strip()
            context.user_data['pick_alto'] = partes_alto[1].strip()
            
            texto_mostrar = context.user_data['pick_oro']
            botones = [
                [InlineKeyboardButton("⚖️ Riesgo Medio", callback_data="ver_medio"), 
                 InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")]
            ]
            teclado = InlineKeyboardMarkup(botones)
        else:
            texto_mostrar = analisis_final
            teclado = None
        
        await mensaje_espera.edit_text(
            text=texto_mostrar,
            reply_markup=teclado,
            parse_mode=None
        )
        
    except Exception as e:
        logger.error(f"Error en el flujo de análisis: {e}")
        await mensaje_espera.edit_text(
            text="⚠️ Ocurrió un error inesperado al procesar tu solicitud. Por favor intenta de nuevo."
        )

# --- NUEVA FUNCIÓN DEL DESPERTADOR MAÑANERO ---
async def pick_automatico(context: ContextTypes.DEFAULT_TYPE):
    mi_chat_id = 7913357339
    
    # Mensaje de aviso mientras la IA piensa
    await context.bot.send_message(
        chat_id=mi_chat_id, 
        text="☀️ ¡Buenos días! Despertando a la IA para buscar tu Pick de Oro de hoy... ⏳"
    )
    
    try:
        # Aquí la IA busca los datos del día
        datos = await obtener_datos_partido("⚽ Fútbol", "Mejores partidos de hoy")
        contexto_datos = construir_prompt_contexto(datos)
        
        # Generamos el análisis real con IA
        analisis_final = await generar_analisis("⚽ Fútbol", "Mejores partidos de hoy", contexto_datos)
        
        mensaje = f"👑 **Pick de Oro Mañanero** 👑\n\n{analisis_final}"
        
    except Exception as e:
        logger.error(f"Error en pick mañanero: {e}")
        mensaje = "👑 **Pick de Oro Mañanero** 👑\n\nNo pude raspar los partidos de hoy automáticamente, mi pa. Échame un partido manual aquí en el chat."

    await context.bot.send_message(chat_id=mi_chat_id, text=mensaje)
# ----------------------------------------------

def main() -> None:
    TOKEN = os.environ.get("TOKEN")
    if not TOKEN:
        logger.critical("Error: La variable de entorno 'TOKEN' no está configurada.")
        sys.exit(1)

    # Iniciar la web fantasma en segundo plano para que Render no cobre
    threading.Thread(target=keep_alive, daemon=True).start()

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    # --- PROGRAMADOR DEL MENSAJE DIARIO ---
    zona_horaria = pytz.timezone('America/Mexico_City')
    hora_despertador = datetime.time(hour=8, minute=0, second=0, tzinfo=zona_horaria)
    application.job_queue.run_daily(pick_automatico, time=hora_despertador)
    # --------------------------------------

    logger.info("Bot de apuestas iniciado en modo gratuito...")
    application.run_polling()

if __name__ == "__main__":
    main()
