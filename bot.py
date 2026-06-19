import sqlite3
import json
import sys
from datetime import datetime, timedelta
import jdatetime
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, 
    ConversationHandler, ContextTypes, filters
)

sys.stdout.reconfigure(encoding='utf-8')

BOT_TOKEN = "794288977:AAEOCb43B9DdNXqhUxs_MQEFelkl81J_1Uw"
DB = "cycles.db"
BASE_WEBAPP_URL = "https://rexybexyspider.github.io/rexybexy.github.io/"

CYCLE = 28
JALALI_MONTHS = [
    'فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور',
    'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'
]

# ─────────────────────── Database ───────────────────────
def init_db():
    with sqlite3.connect(DB) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS cycles (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                start_date TEXT    NOT NULL,
                created_at TEXT    DEFAULT (datetime('now'))
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_uid ON cycles(user_id)")

def db_save(uid: int, date_str: str) -> bool:
    with sqlite3.connect(DB) as c:
        exists = c.execute("SELECT 1 FROM cycles WHERE user_id=? AND start_date=?", (uid, date_str)).fetchone()
        if exists: return False
        c.execute("INSERT INTO cycles(user_id,start_date) VALUES(?,?)", (uid, date_str))
        return True

def db_delete(uid: int, date_str: str) -> bool:
    with sqlite3.connect(DB) as c:
        cursor = c.execute("DELETE FROM cycles WHERE user_id=? AND start_date=?", (uid, date_str))
        return cursor.rowcount > 0

def db_last(uid: int) -> str | None:
    with sqlite3.connect(DB) as c:
        row = c.execute("SELECT start_date FROM cycles WHERE user_id=? ORDER BY start_date DESC LIMIT 1", (uid,)).fetchone()
    return row[0] if row else None

def db_all(uid: int) -> list[str]:
    with sqlite3.connect(DB) as c:
        rows = c.execute("SELECT start_date FROM cycles WHERE user_id=? ORDER BY start_date DESC", (uid,)).fetchall()
    return [r[0] for r in rows]

def db_count(uid: int) -> int:
    with sqlite3.connect(DB) as c:
        return c.execute("SELECT COUNT(*) FROM cycles WHERE user_id=?", (uid,)).fetchone()[0]

# ─────────────────────── Helpers ───────────────────────
def persian_num(n: int) -> str:
    return str(n).translate(str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹'))

def format_date(d: datetime) -> str:
    jd = jdatetime.date.fromgregorian(day=d.day, month=d.month, year=d.year)
    return f"{persian_num(jd.day)} {JALALI_MONTHS[jd.month-1]} {persian_num(jd.year)}"

def get_phase(day: int) -> tuple[str, str]:
    if day <= 0: return "ثبت نشده", "⬜"
    if day <= 5: return "قاعدگی", "🩸"
    if day <= 9: return "پس از قاعدگی", "✨"
    if day <= 17: return "باروری", "💫"
    if day <= 20: return "پس از تخمک‌گذاری", "🌿"
    if day <= 28: return "پیش از قاعدگی", "🌙"
    return "تأخیر", "⚠️"

def get_avg_cycle(uid: int) -> int:
    logs = db_all(uid)
    if len(logs) < 2: return CYCLE
    diffs = []
    for i in range(len(logs)-1):
        d1 = datetime.strptime(logs[i], "%Y-%m-%d")
        d2 = datetime.strptime(logs[i+1], "%Y-%m-%d")
        diffs.append((d1 - d2).days)
    return round(sum(diffs) / len(diffs)) if diffs else CYCLE

def get_main_keyboard(uid: int) -> ReplyKeyboardMarkup:
    user_logs = db_all(uid)
    logs_str = ",".join(user_logs)
    dynamic_url = f"{BASE_WEBAPP_URL}?logs={logs_str}"
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛍 مشاهده تقویم و جزئیات", web_app=WebAppInfo(url=dynamic_url))],
        [KeyboardButton("🩸 ثبت شروع چرخه")],
        [KeyboardButton("📊 گزارش متنی"), KeyboardButton("🗑 مدیریت چرخه‌ها")],
        [KeyboardButton("ℹ️ درباره دنا"), KeyboardButton("🔄 شروع مجدد ربات")]
    ], resize_keyboard=True, is_persistent=True)

def get_back_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["🔙 بازگشت به صفحه اصلی"]], resize_keyboard=True)

# ─────────────────────── Command Handlers ───────────────────────
async def send_main_menu(update: Update, uid: int, name: str):
    last = db_last(uid)
    count = db_count(uid)
    if last:
        ld = datetime.strptime(last, "%Y-%m-%d")
        day = (datetime.now() - ld).days + 1
        phase, emoji = get_phase(day)
        status = f"📍 *وضعیت فعلی:*\n{emoji} روز {persian_num(day)} — {phase}\n📊 چرخه‌های ثبت‌شده: {persian_num(count)}"
    else:
        status = "⚡ هنوز هیچ قاعدگی‌ای ثبت نشده. از دکمه ثبت شروع کن!"
    text = f"💕 *سلام {name} جان!*\n\nمن دُنا هستم، دستیار چرخه قاعدگی‌ات 🌸\n\n{status}\n\nاز منوی اصلی زیر استفاده کن:"
    await update.message.reply_text(text, reply_markup=get_main_keyboard(uid), parse_mode="Markdown")

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, update.effective_user.id, update.effective_user.first_name or "عزیزم")

# ─────────────────────── Manual Logging Flow ───────────────────────
WAIT_CHOICE, ASK_M, ASK_D, ASK_Y, CONFIRM_DATE = range(5)

async def log_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now()
    today_fa = format_date(today)
    context.user_data['today_greg'] = today.strftime("%Y-%m-%d")
    
    kb = [
        [KeyboardButton(f"✅ ثبت امروز ({today_fa})")],
        [KeyboardButton("📅 انتخاب یک تاریخ دیگر")],
        [KeyboardButton("🔙 بازگشت به صفحه اصلی")]
    ]
    await update.message.reply_text("🌸 چه تاریخی را می‌خواهی ثبت کنی؟", reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True))
    return WAIT_CHOICE

async def log_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    
    if text == "🔙 بازگشت به صفحه اصلی":
        await send_main_menu(update, uid, update.effective_user.first_name)
        return ConversationHandler.END
        
    if "✅ ثبت امروز" in text:
        saved = db_save(uid, context.user_data['today_greg'])
        msg = "✅ با موفقیت ثبت شد 🌸" if saved else "ℹ️ این تاریخ قبلاً ثبت شده بود."
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(uid))
        return ConversationHandler.END
        
    elif text == "📅 انتخاب یک تاریخ دیگر":
        await update.message.reply_text(
            "لطفاً **ماه** شروع قاعدگی را به صورت عدد وارد کن (مثلاً برای خرداد عدد 3 را بفرست):",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )
        return ASK_M

async def ask_month(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به صفحه اصلی":
        await send_main_menu(update, update.effective_user.id, update.effective_user.first_name)
        return ConversationHandler.END
        
    if not text.isdigit() or not (1 <= int(text) <= 12):
        await update.message.reply_text("⚠️ عدد ماه نامعتبر است. لطفاً عددی بین 1 تا 12 بفرست:")
        return ASK_M
        
    context.user_data['log_month'] = int(text)
    await update.message.reply_text("حالا **روز** شروع قاعدگی را به صورت عدد وارد کن (مثلاً 15):", parse_mode="Markdown")
    return ASK_D

async def ask_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به صفحه اصلی":
        await send_main_menu(update, update.effective_user.id, update.effective_user.first_name)
        return ConversationHandler.END
        
    if not text.isdigit() or not (1 <= int(text) <= 31):
        await update.message.reply_text("⚠️ عدد روز نامعتبر است. لطفاً عددی بین 1 تا 31 بفرست:")
        return ASK_D
        
    context.user_data['log_day'] = int(text)
    await update.message.reply_text("و در آخر، **سال** را وارد کن (مثلاً 1403):", parse_mode="Markdown")
    return ASK_Y

async def ask_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "🔙 بازگشت به صفحه اصلی":
        await send_main_menu(update, update.effective_user.id, update.effective_user.first_name)
        return ConversationHandler.END
        
    if not text.isdigit() or len(text) != 4:
        await update.message.reply_text("⚠️ سال نامعتبر است. لطفاً یک سال 4 رقمی بفرست (مثلاً 1403):")
        return ASK_Y
        
    context.user_data['log_year'] = int(text)
    jy = context.user_data['log_year']
    jm = context.user_data['log_month']
    jd = context.user_data['log_day']

    try:
        # تبدیل هوشمند و اعتبارسنجی
        date_obj = jdatetime.date(jy, jm, jd)
        greg_date = date_obj.togregorian()
        context.user_data['log_greg_str'] = greg_date.strftime("%Y-%m-%d")
        date_fa = f"{persian_num(jd)} {JALALI_MONTHS[jm-1]} {persian_num(jy)}"

        kb = [
            [KeyboardButton("✅ بله، ثبت کن")],
            [KeyboardButton("✏️ ویرایش (انتخاب مجدد)")],
            [KeyboardButton("🔙 بازگشت به صفحه اصلی")]
        ]
        await update.message.reply_text(
            f"آیا تاریخ **{date_fa}** صحیح است؟", 
            reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True), 
            parse_mode="Markdown"
        )
        return CONFIRM_DATE

    except ValueError:
        await update.message.reply_text("⚠️ تاریخی که وارد کردی در تقویم وجود ندارد! لطفاً دوباره از **ماه** شروع کن:", parse_mode="Markdown")
        return ASK_M

async def confirm_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    
    if text == "🔙 بازگشت به صفحه اصلی":
        await send_main_menu(update, uid, update.effective_user.first_name)
        return ConversationHandler.END
        
    elif text == "✅ بله، ثبت کن":
        date_str = context.user_data['log_greg_str']
        saved = db_save(uid, date_str)
        msg = "✅ تاریخ با موفقیت در پایگاه داده ثبت شد 🌸" if saved else "ℹ️ این تاریخ قبلاً ثبت شده بود."
        await update.message.reply_text(msg, reply_markup=get_main_keyboard(uid))
        return ConversationHandler.END
        
    elif text == "✏️ ویرایش (انتخاب مجدد)":
        await update.message.reply_text("مشکلی نیست. لطفاً **ماه** را دوباره به عدد وارد کن:", reply_markup=get_back_keyboard(), parse_mode="Markdown")
        return ASK_M

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_main_menu(update, update.effective_user.id, update.effective_user.first_name)
    return ConversationHandler.END

# ─────────────────────── Standard Text Handlers ───────────────────────
async def handle_text_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    name = update.effective_user.first_name or "عزیزم"

    if text in ["🔙 بازگشت به صفحه اصلی", "🔄 شروع مجدد ربات"]:
        await send_main_menu(update, uid, name)

    elif text == "📊 گزارش متنی":
        last = db_last(uid)
        if not last:
            await update.message.reply_text("⚠️ هنوز هیچ قاعدگی‌ای ثبت نشده.", reply_markup=get_back_keyboard())
            return
        
        ld = datetime.strptime(last, "%Y-%m-%d")
        day = (datetime.now() - ld).days + 1
        phase, emoji = get_phase(day)
        avg = get_avg_cycle(uid)
        next_p = ld + timedelta(days=avg)
        
        await update.message.reply_text(
            f"📊 *گزارش چرخه شما*\n\n"
            f"{emoji} امروز: روز {persian_num(day)} چرخه ({phase})\n"
            f"🗓 آخرین قاعدگی: {format_date(ld)}\n"
            f"🔮 پیش‌بینی قاعدگی بعدی: {format_date(next_p)}",
            reply_markup=get_back_keyboard(),
            parse_mode="Markdown"
        )

    elif text == "ℹ️ درباره دنا":
        await update.message.reply_text("طراحی شده با عشق برای F ❤️", reply_markup=get_back_keyboard())

    elif text == "🗑 مدیریت چرخه‌ها":
        logs = db_all(uid)
        if not logs:
            await update.message.reply_text("❌ هیچ چرخه‌ای ثبت نشده است.", reply_markup=get_back_keyboard())
            return

        kb_inline = []
        for log in logs[:5]:
            d = datetime.strptime(log, "%Y-%m-%d")
            kb_inline.append([InlineKeyboardButton(f"🗑 حذف {format_date(d)}", callback_data=f"del_req|{log}")])

        await update.message.reply_text("برای حذف، روی تاریخ مورد نظر از منوی شیشه‌ای زیر کلیک کنید:", reply_markup=get_back_keyboard())
        await update.message.reply_text("لیست تاریخ‌های اخیر:", reply_markup=InlineKeyboardMarkup(kb_inline))

# ─────────────────────── Inline Button Callback ───────────────────────
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    uid = q.from_user.id
    data = q.data

    if data.startswith("del_req|"):
        date_str = data.split("|")[1]
        kb = [
            [InlineKeyboardButton("✅ بله، مطمئنم حذف شود", callback_data=f"del_conf|{date_str}")],
            [InlineKeyboardButton("❌ خیر، لغو", callback_data="cancel_del")]
        ]
        await q.edit_message_text(f"⚠️ آیا از حذف این چرخه مطمئنید؟", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("del_conf|"):
        date_str = data.split("|")[1]
        db_delete(uid, date_str)
        await q.edit_message_text("✅ تاریخ با موفقیت از سیستم حذف شد.")
        await context.bot.send_message(chat_id=uid, text="🔄 لیست به‌روزرسانی شد. می‌توانی از منوی پایین ادامه دهی.", reply_markup=get_main_keyboard(uid))

    elif data == "cancel_del":
        await q.edit_message_text("❌ عملیات لغو شد.")

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    
    # اضافه کردن هندلر گفتگوی مرحله به مرحله برای ثبت تاریخ
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🩸 ثبت شروع چرخه$"), log_start)],
        states={
            WAIT_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_choice)],
            ASK_M: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_month)],
            ASK_D: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_day)],
            ASK_Y: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_year)],
            CONFIRM_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_manual)],
        },
        fallbacks=[MessageHandler(filters.Regex("^(🔙 بازگشت به صفحه اصلی|🔄 شروع مجدد ربات)$"), cancel_conv)]
    )
    
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_buttons))
    
    print("🌸 دُنا روشن و آماده کار است...")
    app.run_polling()

if __name__ == "__main__":
    main()