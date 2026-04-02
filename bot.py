import telebot
import requests
import time

# ==========================================
# 1. الإعدادات الأساسية
# ==========================================
BOT_TOKEN = "TELE_BOT_API_KEY_HERE" 
API_URL = "http://127.0.0.1:7777/v1/chat/completions"
# تأكد أن هذا المفتاح هو نفس الموجود في ملف main.py
API_KEY = "Dowedar" 

bot = telebot.TeleBot(BOT_TOKEN)

# ==========================================
# 2. هندسة الهوية والذاكرة (System Prompt)
# ==========================================
UNIVY_SYSTEM_PROMPT = """
أنت الآن "Univy"، مساعد أكاديمي تعليمي ذكي ومتطور، تم تطويرك بواسطة Dowedar وفريق من طلاب قسم الحاسب الآلي بكلية التربية النوعية جامعة دمياط.
هويتك هي: مساعد أكاديمي متخصص في مساعدة الطلاب والباحثين.

قواعد صارمة للإجابة:
1. استخدم لغة عربية فصيحة، بسيطة، ومباشرة.
2. قدم إجاباتك بشكل منظم في نقاط لتسهيل القراءة.
3. إذا طلب منك الطالب شرح معقد، قم بتحليله خطوة بخطوة.
4. إذا لم تكن متأكداً من معلومة علمية، اطلب من الطالب توضيحها ولا تقم بتأليف معلومات خاطئة.
5. حافظ دائماً على هويتك كـ Univy.
"""

user_sessions = {}

def get_chat_history(chat_id):
    """إرجاع تاريخ المحادثة أو إنشاء واحد جديد يبدأ بالـ System Prompt"""
    if chat_id not in user_sessions:
        user_sessions[chat_id] = [
            {"role": "system", "content": UNIVY_SYSTEM_PROMPT}
        ]
    return user_sessions[chat_id]

def append_to_history(chat_id, role, content):
    """إضافة رسالة للذاكرة مع الحفاظ على آخر 10 رسائل فقط"""
    history = get_chat_history(chat_id)
    history.append({"role": role, "content": content})
    
    # نحتفظ بالـ System Prompt (أول عنصر) + آخر 10 رسائل فقط
    if len(history) > 11:
        user_sessions[chat_id] = [history[0]] + history[-10:]

# ==========================================
# 3. أوامر البوت
# ==========================================
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    # تصفير الذاكرة عند بدء محادثة جديدة
    user_sessions[chat_id] = [{"role": "system", "content": UNIVY_SYSTEM_PROMPT}]
    
    welcome_text = (
        "أهلاً بك في 🎓 Univy Pro\n\n"
        "أنا المساعد الأكاديمي الذكي الخاص بك، تم تطويري بواسطة Dowedar لمساعدتك في أبحاثك ودراستك.\n\n"
        "اسألني أي سؤال علمي أو اطلب مني شرح أي مفهوم!"
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['clear'])
def clear_history(message):
    chat_id = message.chat.id
    user_sessions[chat_id] = [{"role": "system", "content": UNIVY_SYSTEM_PROMPT}]
    bot.reply_to(message, "🧹 تم مسح ذاكرة المحادثة بنجاح. يمكننا البدء في موضوع جديد!")

# ==========================================
# 4. معالجة الرسائل والاتصال بالسيرفر
# ==========================================
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    chat_id = message.chat.id
    user_text = message.text

    # رسالة مؤقتة
    processing_msg = bot.reply_to(message, "⏳ Univy يفكر...")

    # إضافة سؤال الطالب للذاكرة
    append_to_history(chat_id, "user", user_text)

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gemini-2.0-flash",
        "messages": get_chat_history(chat_id)
    }

    try:
        # إرسال المحادثة للسيرفر مع مهلة 3 دقائق (180 ثانية)
        response = requests.post(API_URL, json=payload, headers=headers, timeout=180)
        
        if response.status_code == 200:
            response_data = response.json()
            reply_text = response_data['choices'][0]['message']['content']

            # إضافة إجابة Univy للذاكرة
            append_to_history(chat_id, "assistant", reply_text)

            # إرسال الرد بدون parse_mode لتجنب أخطاء ماركداون تيليجرام
            bot.edit_message_text(chat_id=chat_id, 
                                  message_id=processing_msg.message_id, 
                                  text=reply_text)
        else:
            raise Exception(f"API Error: Status {response.status_code}")
                              
    except Exception as e:
        print(f"Error processing request: {e}")
        # لو حصل خطأ، نمسح سؤال الطالب من الذاكرة
        if len(user_sessions[chat_id]) > 1:
            user_sessions[chat_id].pop() 
            
        bot.edit_message_text(chat_id=chat_id, 
                              message_id=processing_msg.message_id, 
                              text="❌ عذراً، حدث خطأ في الاتصال بالسيرفر الأكاديمي.\nتأكد من تشغيل السيرفر ومن استقرار الإنترنت لديك.")

# ==========================================
# 5. تشغيل البوت (حماية ضد قطع الإنترنت)
# ==========================================
print("=========================================")
print("🎓 [UNIVY BOT] Started successfully!")
print("⏳ Waiting for messages from Telegram...")
print("=========================================")

while True:
    try:
        # مهلة الاتصال 90 ثانية لتقليل التقطيع بسبب النت الضعيف
        bot.polling(none_stop=True, timeout=90, long_polling_timeout=90)
    except Exception as e:
        print(f"\n⚠️ [UNIVY BOT] Connection dropped: {e}")
        print("🔄 [UNIVY BOT] Reconnecting in 5 seconds...")
        time.sleep(5)