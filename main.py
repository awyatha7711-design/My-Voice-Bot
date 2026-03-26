import os
import asyncio
import io
from flask import Flask
from threading import Thread
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
import google.generativeai as genai

# --- CONFIGURATION ---
TOKEN = os.getenv("BOT_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
CHANNEL_ID = "@reeac_99"

# Gemini Setup
genai.configure(api_key=GEMINI_KEY)

# Flask Server for Render
app = Flask('')
@app.route('/')
def home(): return "Gemini TTS Bot is Online"
def run(): app.run(host='0.0.0.0', port=10000)

JOIN_CHECK, GET_TEXT, SELECT_VOICE = range(3)

# Gemini Official Voices (၁၀ မျိုး) - မြန်မာလို အကောင်းဆုံးဖတ်နိုင်သော အသံများ
GEMINI_VOICES = {
    "Aoede (Female - ချစ်စရာကောင်းသော)": "aoede",
    "Kore (Female - ကြည်လင်သော)": "kore",
    "Europa (Female - အေးချမ်းသော)": "europa",
    "Harpalyke (Female - နူးညံ့သော)": "harpalyke",
    "Isonoe (Female - တက်ကြွသော)": "isonoe",
    "Puck (Male - Creator သံ)": "puck",
    "Charon (Male - အသံသြဇာရှိသော)": "charon",
    "Kallichore (Male - သဘာဝကျသော)": "kallichore",
    "Ganymede (Male - တည်ငြိမ်သော)": "ganymede",
    "Enceladus (Male - ပညာရှင်သံ)": "enceladus"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['left', 'kicked']:
            keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                        [InlineKeyboardButton("I have joined ✅", callback_data="check_join")]]
            await update.message.reply_text("ရှေ့ဆက်ဖို့ Channel အရင် Join ပေးပါ။", reply_markup=InlineKeyboardMarkup(keyboard))
            return JOIN_CHECK
        await update.message.reply_text("Gemini Smart Voice Bot မှ ကြိုဆိုပါတယ်။\nအသံပြောင်းလိုသော စာသားကို ရိုက်ထည့်ပေးပါ။")
        return GET_TEXT
    except:
        await update.message.reply_text("Error: Bot ကို Channel မှာ Admin ခန့်ထားပါသလား ပြန်စစ်ပေးပါ။")
        return ConversationHandler.END

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=query.from_user.id)
    if member.status not in ['left', 'kicked']:
        await query.message.delete()
        await context.bot.send_message(chat_id=query.from_user.id, text="စာသားကို ရိုက်ထည့်နိုင်ပါပြီ။")
        return GET_TEXT
    return JOIN_CHECK

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['text_to_convert'] = update.message.text
    keyboard = []
    v_keys = list(GEMINI_VOICES.keys())
    for i in range(0, len(v_keys), 2):
        row = [InlineKeyboardButton(v_keys[i], callback_data=v_keys[i])]
        if i+1 < len(v_keys): row.append(InlineKeyboardButton(v_keys[i+1], callback_data=v_keys[i+1]))
        keyboard.append(row)
    await update.message.reply_text("အသုံးပြုလိုသော Gemini အသံကို ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_VOICE

async def handle_voice_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    voice_display_name = query.data
    voice_id = GEMINI_VOICES[voice_display_name]
    text = context.user_data.get('text_to_convert')
    await query.answer()
    
    msg = await query.edit_message_text(f"⏳ {voice_display_name} ဖြင့် အသံဖန်တီးနေပါသည်...")

    try:
        # Gemini API Multimodal Generation
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        # Gemini ရဲ့ Speech Synthesis ကို ခေါ်ယူခြင်း
        response = model.generate_content(
            contents=text,
            generation_config={"speech_config": {"voice_config": {"prebuilt_voice_id": voice_id}}}
        )

        # Audio Data ကို ဖတ်ယူခြင်း
        audio_data = response.executable_ad_data.audio_content
        if audio_data:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "gemini_voice.mp3"
            await query.message.reply_audio(audio=audio_file, caption=f"🎙 Gemini Voice: {voice_display_name}")
            await msg.delete()
        else:
            await query.edit_message_text("Error: Gemini မှ အသံဒေတာ မရရှိပါ။")
    except Exception as e:
        await query.edit_message_text(f"Error: {str(e)}")
    
    return GET_TEXT

def main():
    Thread(target=run).start()
    application = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            JOIN_CHECK: [CallbackQueryHandler(check_join_callback, pattern="^check_join$")],
            GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            SELECT_VOICE: [CallbackQueryHandler(handle_voice_selection)]
        },
        fallbacks=[CommandHandler("start", start)]
    )
    application.add_handler(conv_handler)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
