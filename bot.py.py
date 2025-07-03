
import os
import shutil
import random
import string
import pyminizip
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

# Estados por usuario
usuarios = {}

# Carpeta base para guardar archivos
BASE_DIR = "archivos_bot"
os.makedirs(BASE_DIR, exist_ok=True)

# Generar teclado con botones
def get_botones():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Terminar y enviar", callback_data="terminar_envio")],
        [
            InlineKeyboardButton("/reiniciar", switch_inline_query_current_chat="/reiniciar"),
            InlineKeyboardButton("/cancelar", switch_inline_query_current_chat="/cancelar")
        ]
    ])

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("¡Hola! Envía el nombre que tendrá tu archivo ZIP.")

# Guardar nombre del archivo
async def guardar_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    nombre = update.message.text.strip().replace(" ", "_")

    carpeta = os.path.join(BASE_DIR, f"user_{user_id}")
    os.makedirs(carpeta, exist_ok=True)

    usuarios[user_id] = {
        "nombre_zip": nombre,
        "carpeta": carpeta,
        "contador": 0,
        "mensaje_progreso_id": None
    }

    await update.message.reply_text(
        f"📝 Nombre asignado: *{nombre}*\nAhora envía las fotos o videos.",
        parse_mode="Markdown",
        reply_markup=get_botones()
    )

# Recibir archivos
async def recibir_archivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    estado = usuarios.get(user_id)

    if not estado:
        await update.message.reply_text("⚠️ Escribe primero un nombre para el archivo ZIP.")
        return

    archivo = None
    extension = ""
    if update.message.photo:
        archivo = await update.message.photo[-1].get_file()
        extension = ".jpg"
    elif update.message.video:
        archivo = await update.message.video.get_file()
        extension = ".mp4"
    else:
        return

    estado["contador"] += 1
    nombre_archivo = f"{estado['contador']}{extension}"
    ruta = os.path.join(estado["carpeta"], nombre_archivo)
    await archivo.download_to_drive(ruta)

    texto_estado = f"📤 Subiendo archivos ({estado['contador']})"
    if estado["mensaje_progreso_id"]:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=estado["mensaje_progreso_id"],
                text=texto_estado
            )
        except:
            pass
    else:
        msg = await update.message.reply_text(texto_estado)
        estado["mensaje_progreso_id"] = msg.message_id

    # Mostrar “Archivos listos” después de cierto delay
    context.job_queue.run_once(
        mostrar_listo,
        2,
        chat_id=update.effective_chat.id,
        name=str(user_id),
        data={"user_id": user_id, "msg_id": estado["mensaje_progreso_id"]}
    )

# Mostrar "Archivos listos"
async def mostrar_listo(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data["user_id"]
    msg_id = context.job.data["msg_id"]
    estado = usuarios.get(user_id)

    if estado and estado["mensaje_progreso_id"] == msg_id:
        await context.bot.edit_message_text(
            chat_id=context.job.chat_id,
            message_id=msg_id,
            text="✅ Archivos listos"
        )
        estado["mensaje_progreso_id"] = None

# Reiniciar
async def reiniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    estado = usuarios.get(user_id)
    if estado and os.path.exists(estado["carpeta"]):
        shutil.rmtree(estado["carpeta"])
    usuarios.pop(user_id, None)
    await update.message.reply_text("🔄 Proceso reiniciado. Escribe un nuevo nombre.")

# Cancelar
async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await reiniciar(update, context)
    await update.message.reply_text("❌ Proceso cancelado.")

# Terminar (desde botón o comando)
async def terminar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    estado = usuarios.get(user_id)

    if not estado or not estado["nombre_zip"] or not estado["carpeta"]:
        mensaje = "⚠️ No hay archivos guardados. Escribe un nombre primero."
        if update.callback_query:
            await update.callback_query.message.reply_text(mensaje)
        else:
            await update.message.reply_text(mensaje)
        return

    nombre = estado["nombre_zip"]
    zip_path = os.path.join(BASE_DIR, f"{nombre}.zip")
    files, names = [], []

    for archivo in os.listdir(estado["carpeta"]):
        ruta = os.path.join(estado["carpeta"], archivo)
        files.append(ruta)
        names.append(archivo)

    password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    pyminizip.compress_multiple(files, names, zip_path, password, 5)

    await context.bot.send_document(
        chat_id=ADMIN_CHAT_ID,
        document=open(zip_path, 'rb'),
        caption=f"📦 ZIP de {update.effective_user.first_name}:\n`{nombre}.zip`\n🔑 Contraseña: `{password}`",
        parse_mode="Markdown"
    )

    msg = "📬 Archivos enviados con contraseña. ¡Gracias!"
    if update.callback_query:
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)

    shutil.rmtree(estado["carpeta"])
    os.remove(zip_path)
    usuarios.pop(user_id, None)

# Botón callback
async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query.data == "terminar_envio":
        await terminar(update, context)

# Lanzar bot
app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("reiniciar", reiniciar))
app.add_handler(CommandHandler("cancelar", cancelar))
app.add_handler(CommandHandler("terminar", terminar))
app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), guardar_nombre))
app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO, recibir_archivo))
app.add_handler(CallbackQueryHandler(callback))

print("🤖 Bot corriendo...")
app.run_polling()
