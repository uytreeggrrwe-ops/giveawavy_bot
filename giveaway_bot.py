import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import random
import threading
import time

TOKEN = "8897612396:AAFv-YOEAW3IYIGGuAfxUO-xezUZ6k5YiBg"

bot = telebot.TeleBot(TOKEN)
giveaways = {}
user_channels = {}
user_state = {}

@bot.message_handler(commands=['start'])
def start(message):
    text = """🎁 بوت السحوبات العام

الأوامر:
- /setchannel @القناة : ربط قناتك للتحقق
- /newgiveaway : بدء سحب جديد
- /draw : سحب الفائزين يدوياً
- /cancel : إلغاء السحب"""
    bot.reply_to(message, text)

@bot.message_handler(commands=['setchannel'])
def set_channel(message):
    user_id = message.from_user.id
    try:
        channel = message.text.split()[1].replace("@", "")
        user_channels[user_id] = channel
        bot.reply_to(message, f"✅ تم ربط قناتك: @{channel}")
    except:
        bot.reply_to(message, "❌ الاستخدام: /setchannel @اسم_القناة")

@bot.message_handler(commands=['newgiveaway'])
def new_giveaway(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if chat_id in giveaways and giveaways[chat_id]["active"]:
        bot.reply_to(message, "❌ يوجد سحب نشط في هذا القروب")
        return

    user_state[user_id] = {"step": "awaiting_winners", "chat_id": chat_id}

    markup = InlineKeyboardMarkup(row_width=4)
    markup.add(
        InlineKeyboardButton("1", callback_data="winners_1"),
        InlineKeyboardButton("2", callback_data="winners_2"),
        InlineKeyboardButton("3", callback_data="winners_3"),
        InlineKeyboardButton("5", callback_data="winners_5"),
        InlineKeyboardButton("10", callback_data="winners_10"),
        InlineKeyboardButton("20", callback_data="winners_20")
    )
    bot.reply_to(message, "🎯 اختر عدد الفائزين:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("winners_"))
def set_winners(call):
    user_id = call.from_user.id
    if user_id not in user_state:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة")
        return

    winners_count = int(call.data.split("_")[1])
    user_state[user_id]["winners"] = winners_count
    user_state[user_id]["step"] = "awaiting_type"

    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🎯 يدوي", callback_data="type_manual"),
        InlineKeyboardButton("⏰ تلقائي", callback_data="type_auto")
    )
    bot.edit_message_text(
        f"✅ عدد الفائزين: {winners_count}\nاختر نوع السحب:",
        call.message.chat.id, call.message_id, reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("type_"))
def set_type(call):
    user_id = call.from_user.id
    if user_id not in user_state:
        bot.answer_callback_query(call.id, "❌ انتهت الجلسة")
        return

    gtype = call.data.split("_")[1]
    user_state[user_id]["type"] = gtype

    if gtype == "manual":
        user_state[user_id]["step"] = "awaiting_template"
        bot.edit_message_text("📝 أرسل الآن نص السحب:", call.message.chat.id, call.message_id)
    else:
        user_state[user_id]["step"] = "awaiting_time"
        bot.edit_message_text("⏰ أرسل وقت السحب بالدقائق\nمثال: 60 يعني بعد ساعة", call.message.chat.id, call.message_id)

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "awaiting_time")
def set_time(message):
    user_id = message.from_user.id
    try:
        minutes = int(message.text)
        if minutes < 1: raise ValueError
        user_state[user_id]["minutes"] = minutes
        user_state[user_id]["step"] = "awaiting_template"
        bot.reply_to(message, f"✅ السحب بعد {minutes} دقيقة\n📝 أرسل الآن نص السحب:")
    except:
        bot.reply_to(message, "❌ أرسل رقم صحيح للدقائق")

@bot.message_handler(func=lambda m: user_state.get(m.from_user.id, {}).get("step") == "awaiting_template")
def set_template(message):
    user_id = message.from_user.id
    chat_id = user_state[user_id]["chat_id"]
    winners = user_state[user_id]["winners"]
    gtype = user_state[user_id]["type"]
    template = message.text

    giveaways[chat_id] = {
        "participants": [],
        "active": True,
        "template": template,
        "owner": user_id,
        "winners_count": winners,
        "type": gtype,
        "message_id": None
    }

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 انضم للسحب", callback_data="join"))

    msg = bot.send_message(chat_id, f"{template}\n\n👇 اضغط للانضمام", reply_markup=markup)
    giveaways[chat_id]["message_id"] = msg.message_id

    if gtype == "auto":
        minutes = user_state[user_id]["minutes"]
        giveaways[chat_id]["end_time"] = time.time() + (minutes * 60)
        timer = threading.Timer(minutes * 60, lambda: auto_draw(chat_id))
        timer.start()
        giveaways[chat_id]["timer"] = timer
        bot.reply_to(message, f"✅ تم نشر السحب التلقائي - ينتهي بعد {minutes} دقيقة")
    else:
        bot.reply_to(message, f"✅ تم نشر السحب اليدوي - اكتب /draw للسحب")

    user_state.pop(user_id)

def auto_draw(chat_id):
    if chat_id in giveaways and giveaways[chat_id]["active"]:
        pick_winners(chat_id)
        bot.send_message(chat_id, "⏰ انتهى وقت السحب وتم السحب تلقائياً")

@bot.callback_query_handler(func=lambda call: call.data == "join")
def join(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if chat_id not in giveaways or not giveaways[chat_id]["active"]:
        bot.answer_callback_query(call.id, "❌ لا يوجد سحب نشط")
        return

    owner_id = giveaways[chat_id]["owner"]
    channel = user_channels.get(owner_id)

    if channel:
        try:
            member = bot.get_chat_member(f"@{channel}", user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                bot.answer_callback_query(call.id, f"❌ لازم تشترك في @{channel} أولاً", show_alert=True)
                return
        except:
            bot.answer_callback_query(call.id, "❌ تأكد أن البوت مشرف في القناة", show_alert=True)
            return

    if user_id in giveaways[chat_id]["participants"]:
        bot.answer_callback_query(call.id, "⚠️ أنت مشترك بالفعل")
        return

    giveaways[chat_id]["participants"].append(user_id)
    bot.answer_callback_query(call.id, "✅ تم تسجيلك في السحب")

    count = len(giveaways[chat_id]["participants"])

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 انضم للسحب", callback_data="join"))
    if call.from_user.id == owner_id:
        markup.add(InlineKeyboardButton("📋 إرسال القائمة", callback_data="send_list"))

    bot.edit_message_text(
        f"{giveaways[chat_id]['template']}\n\n👇 اضغط للانضمام\n👥 المشاركين: {count}",
        chat_id, call.message_id, reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "send_list")
def send_list(call):
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if chat_id not in giveaways or giveaways[chat_id]["owner"]!= user_id:
        bot.answer_callback_query(call.id, "❌ للأدمن فقط", show_alert=True)
        return

    participants = giveaways[chat_id]["participants"]
    if not participants:
        bot.answer_callback_query(call.id, "❌ لا يوجد مشاركين", show_alert=True)
        return

    list_text = f"📋 قائمة المشتركين - العدد: {len(participants)}\n\n"
    for i, uid in enumerate(participants, 1):
        try:
            user = bot.get_chat(uid)
            name = user.first_name or "بدون اسم"
            username = f"@{user.username}" if user.username else "بدون معرف"
            list_text += f"{i}. {name} | {username} | `{uid}`\n"
        except:
            list_text += f"{i}. مجهول | `{uid}`\n"

    try:
        bot.send_message(user_id, list_text, parse_mode="Markdown")
        bot.answer_callback_query(call.id, "✅ تم إرسال القائمة على الخاص")
    except:
        bot.answer_callback_query(call.id, "❌ ما قدرت أرسل لك. ابدأ محادثة مع البوت أولاً", show_alert=True)

@bot.message_handler(commands=['draw'])
def draw(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id not in giveaways:
        bot.reply_to(message, "❌ لا يوجد سحب نشط")
        return

    if giveaways[chat_id]["owner"]!= user_id:
        bot.reply_to(message, "❌ هذا السحب مو لك")
        return

    pick_winners(chat_id)

def pick_winners(chat_id):
    participants = giveaways[chat_id]["participants"]
    winners_count = giveaways[chat_id]["winners_count"]

    if not participants:
        bot.send_message(chat_id, "❌ لا يوجد مشاركين")
        return

    if winners_count > len(participants):
        winners_count = len(participants)

    winners = random.sample(participants, winners_count)
    winners_text = "\n".join([f"{i+1}. [{uid}](tg://user?id={uid})" for i, uid in enumerate(winners)])

    bot.send_message(chat_id, f"🎊 مبروك للفائزين:\n{winners_text}", parse_mode="Markdown")
    giveaways[chat_id]["active"] = False

    if "timer" in giveaways[chat_id]:
        giveaways[chat_id]["timer"].cancel()

@bot.message_handler(commands=['cancel'])
def cancel(message):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if chat_id in giveaways and giveaways[chat_id]["owner"] == user_id:
        if "timer" in giveaways[chat_id]:
            giveaways[chat_id]["timer"].cancel()
        giveaways.pop(chat_id)
        bot.reply_to(message, "✅ تم إلغاء السحب")
    else:
        bot.reply_to(message, "❌ ما عندك سحب نشط تلغيه")

bot.infinity_polling()