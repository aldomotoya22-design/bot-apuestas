import logging
import os
import sys
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

    elif data == "picks_valor":
        mensaje_respuesta = (
            "🔥 *Buscando Picks de Alto Valor Hoy...*\n\n"
            "Conectando a los algoritmos cuantitativos (+EV)... (Fase 2)"
        )
        teclado_volver = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Volver al menú", callback_data="volver_menu")]
        ])
        await query.edit_message_text(
            text=mensaje_respuesta, 
            reply_markup=teclado_volver, 
            parse_mode="Markdown"
        )

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
                 InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")]
            ]
        elif data == "ver_medio":
            texto = context.user_data.get('pick_medio', '⚠️ Pick no encontrado.')
            botones = [
                [InlineKeyboardButton("👑 Pick de Oro", callback_data="ver_oro"), 
                 InlineKeyboardButton("💣 Soñador", callback_data="ver_alto")]
            ]
        elif data == "ver_alto":
            texto = context.user_data.get('pick_alto', '⚠️ Pick no encontrado.')
            botones = [
                [InlineKeyboardButton("👑 Pick de Oro", callback_data="ver_oro"), 
                 InlineKeyboardButton("⚖️ Riesgo Medio", callback_data="ver_medio")]
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

def main() -> None:
    TOKEN = os.environ.get("TOKEN")
    if not TOKEN:
        logger.critical("Error: La variable de entorno 'TOKEN' no está configurada.")
        sys.exit(1)

    application = ApplicationBuilder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot de apuestas iniciado con interfaz interactiva...")
    application.run_polling()

if __name__ == "__main__":
    main()
