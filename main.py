import os
import asyncio
import logging
from flask import Flask
from threading import Thread
import edge_tts
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Flask Server for Render (Port 10000)
app = Flask('')
@app.route('/')
def home(): return "Bot is Online"
def run(): app.run(host='0.0.0.0', port=10000)

# --- CONFIGURATION ---
# Render Environment Variables ထဲမှာ BOT_TOKEN ကို ထည့်ထားပေးပါ
TOKEN = os.getenv("BOT_TOKEN")
# မင်းရဲ့ Channel နာမည်ကို ဒီအောက်မှာ အမှန်ပြင်ပါ (ဥပမာ "@mychannel")
CHANNEL_ID = "@reeac_99" 
# ---------------------

LANG, AUTH, TEXT, VOICE = range(4)

VOICES = {
    "mm": {
        "Nilar (Female)": "my-MM-NilarNeural",
        "Poe (Female)": "en-GB-SoniaNeural",
        "Shwe (Female)": "en-US-EmmaNeural",
        "Aye (Female)": "en-CA-ClaraNeural",
        "May (Female)": "en-AU-NatashaNeural",
        "Thura (Male)": "my-MM-ThihaNeural",
        "Kyaw (Male)": "en-US-GuyNeural",
        "Min (Male)": "en-GB-RyanNeural",
        "Zaw (Male)": "en-AU-WilliamNeural",
        "Htet (Male)": "en-US-ChristopherNeural"
    },
    "en": {
        "Alice (Female)": "en-US-EmmaNeural",
        "Sonia (Female)": "en-GB-SoniaNeural",
        "Clara (Female)": "en-CA-ClaraNeural",
        "Ava (Female)": "en-US-AvaNeural",
        "Natasha (Female)": "en-AU-NatashaNeural",
        "Guy (Male)": "en-US-GuyNeural",
        "Ryan (Male)": "en-GB-RyanNeural",
        "Liam (Male)": "en-CA-LiamNeural",
        "William (Male)": "en-AU-WilliamNeural",
        "Chris (Male)": "en-US-ChristopherNeural"
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("မြန်မာစာ 🇲🇲", callback_data='mm'),
                 InlineKeyboardButton("English 🇺🇸", callback_data='en')]]
    await update.message.reply_text("Please select your language / ဘာသာစကားရွေးချယ်ပါ-", reply_markup=InlineKeyboardMarkup(keyboard))
    return LANG

async def lang_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['lang'] = query.data
    
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.edit_message_text("✅ Verified! Please send the text you want to convert.")
            return TEXT
        else: raise Exception()
    except:
        keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                    [InlineKeyboardButton("✅ Joined (အတည်ပြုမည်)", callback_data='check_join')]]
        await query.edit_message_text(f"You must join our channel {CHANNEL_ID} first!", reply_markup=InlineKeyboardMarkup(keyboard))
        return AUTH

async def check_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    try:
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['member', 'administrator', 'creator']:
            await query.edit_message_text("🎉 Verified Successfully! Send your text now.")
            return TEXT
        else:
            await query.answer("❌ You haven't joined yet!", show_alert=True)
            return AUTH
    except: return AUTH

async def get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['text'] = update.message.text
    lang = context.user_data.get('lang', 'mm')
    buttons = []
    v_keys = list(VOICES[lang].keys())
    for i in range(0, len(v_keys), 2):
        row = [InlineKeyboardButton(v_keys[i], callback_data=v_keys[i])]
        if i+1 < len(v_keys): row.append(InlineKeyboardButton(v_keys[i+1], callback_data=v_keys[i+1]))
        buttons.append(row)
    
    await update.message.reply_text("👤 Select Voice Character:", reply_markup=InlineKeyboardMarkup(buttons))
    return VOICE

async def generate_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    v_name = query.data
    lang = context.user_data.get('lang', 'mm')
    text = context.user_data.get('text')
    v_id = VOICES[lang][v_name]
    
    msg = await query.edit_message_text(f"⏳ Generating audio with {v_name}...")
    file_path = f"audio_{query.from_user.id}.mp3"
    
    try:
        communicate = edge_tts.Communicate(text, v_id)
        await communicate.save(file_path)
        await context.bot.send_audio(chat_id=query.message.chat_id, audio=open(file_path, 'rb'), caption=f"🎙 Voice: {v_name}")
        await msg.delete()
        os.remove(file_path)
    except Exception as e:
        logging.error(f"TTS Error: {e}")
        await query.edit_message_text("❌ Error generating audio. Please try again.")
    
    return TEXT

def main():
    Thread(target=run).start()
    # drop_pending_updates=True က Conflict Error တွေကို ရှင်းပေးပါလိမ့်မယ်
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            LANG: [CallbackQueryHandler(lang_choice, pattern='^(mm|en)$')],
            AUTH: [CallbackQueryHandler(check_join, pattern='^check_join$')],
            TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text)],
            VOICE: [CallbackQueryHandler(generate_audio)]
        },
        fallbacks=[CommandHandler('start', start)]
    )
    
    application.add_handler(conv_handler)
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
