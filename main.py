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

# Flask Server for Render (Keep Alive)
app = Flask('')
@app.route('/')
def home(): return "Gemini TTS Bot is Online"
def run(): app.run(host='0.0.0.0', port=10000)

# States
GET_TEXT, SELECT_VOICE = range(2)

GEMINI_VOICES = {
    "Aoede (Female)": "aoede",
    "Kore (Female)": "kore",
    "Europa (Female)": "europa",
    "Puck (Male)": "puck",
    "Charon (Male)": "charon",
    "Enceladus (Male)": "enceladus"
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        # Channel Join စစ်ဆေးခြင်း
        member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ['left', 'kicked']:
            keyboard = [[InlineKeyboardButton("Join Channel", url=f"https://t.me/{CHANNEL_ID.replace('@','')}")],
                        [InlineKeyboardButton("I have joined ✅", callback_data="check_join")]]
            await update.message.reply_text("ရှေ့ဆက်ဖို့ Channel အရင် Join ပေးပါ။", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END # Join မလုပ်မချင်း ရှေ့မဆက်စေရန်
        
        await update.message.reply_text("Gemini Smart Voice Bot မှ ကြိုဆိုပါတယ်။\nအသံပြောင်းလိုသော စာသားကို ရိုက်ထည့်ပေးပါ။")
        return GET_TEXT
    except Exception as e:
        await update.message.reply_text("Bot ကို Channel မှာ Admin အရင်ခန့်ပေးပါ။")
        return ConversationHandler.END

async def check_join_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    member = await context.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=query.from_user.id)
    if member.status not in ['left', 'kicked']:
        await query.message.edit_text("ကျေးဇူးတင်ပါတယ်။ အခု စာသားရိုက်ထည့်နိုင်ပါပြီ။")
        return GET_TEXT
    else:
        await query.answer("Channel ကို အရင် Join ပါဦး။", show_alert=True)
        return None

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # User ပို့လိုက်တဲ့ စာသားကို သိမ်းထားခြင်း
    context.user_data['text_to_convert'] = update.message.text
    
    keyboard = []
    v_keys = list(GEMINI_VOICES.keys())
    for i in range(0, len(v_keys), 2):
        row = [InlineKeyboardButton(v_keys[i], callback_data=v_keys[i])]
        if i+1 < len(v_keys): row.append(InlineKeyboardButton(v_keys[i+1], callback_data=v_keys[i+1]))
        keyboard.append(row)
    
    await update.message.reply_text("အသုံးပြုလိုသော အသံအမျိုးအစားကို ရွေးချယ်ပါ -", reply_markup=InlineKeyboardMarkup(keyboard))
    return SELECT_VOICE

async def handle_voice_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    voice_display_name = query.data
    voice_id = GEMINI_VOICES.get(voice_display_name)
    text = context.user_data.get('text_to_convert')
    
    await query.answer()
    msg = await query.edit_message_text(f"⏳ {voice_display_name} ဖြင့် ဖန်တီးနေသည်...")

    try:
        # Gemini Multimodal API Call
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # မှတ်ချက် - Gemini TTS API သည် လက်ရှိတွင် တချို့ Region များ၌သာ ရနိုင်ပါသည်
        response = model.generate_content(
            contents=text,
            generation_config={"speech_config": {"voice_config": {"prebuilt_voice_id": voice_id}}}
        )

        # Audio binary data ကို ထုတ်ယူခြင်း
        # အကယ်၍ API က audio content တိုက်ရိုက်မပေးပါက error catch ထဲရောက်သွားပါမည်
        audio_data = response.executable_ad_data.audio_content
        
        if audio_data:
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "voice.mp3"
            await query.message.reply_audio(audio=audio_file, caption=f"🎙 Voice: {voice_display_name}")
            await msg.delete()
        else:
            await query.edit_message_text("Error: Gemini ဘက်မှ အသံဒေတာ မထုတ်ပေးနိုင်ပါ။")
            
    except Exception as e:
        await query.edit_message_text(f"အမှားအယွင်းရှိပါသည်: {str(e)}\n(Gemini API ၏ TTS feature မှာ လက်ရှိတွင် ကန့်သတ်ချက်ရှိနိုင်ပါသည်)")
    
    # နောက်ထပ်စာသား ထပ်ရိုက်နိုင်အောင် GET_TEXT ပြန်ပေးထားခြင်း
    return GET_TEXT

def main():
    # Flask ကို Thread နဲ့ Run ရန်
    Thread(target=run).start()
    
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text) # Start မနှိပ်ဘဲ စာရိုက်ရင်လည်း လက်ခံရန်
        ],
        states={
            GET_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text)],
            SELECT_VOICE: [CallbackQueryHandler(handle_voice_selection)]
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True
    )

    # Check Join အတွက် Callback ကို သီးသန့် Handler အနေနဲ့ ထားပေးခြင်းက ပိုစိတ်ချရပါတယ်
    application.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join$"))
    application.add_handler(conv_handler)
    
    print("Bot is running...")
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
