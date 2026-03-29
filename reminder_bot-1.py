#!/usr/bin/env python3
import logging, json, os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

BOT_TOKEN = "8642080770:AAGNJor8oKX2tUOLmE4rJ21EIaM2pYLs-8s"
TIMEZONE  = "Asia/Tashkent"
DATA_FILE = "reminders.json"

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

(CHOOSING_TYPE, ENTERING_TITLE, ENTERING_DATE, ENTERING_TIME,
 ENTERING_WEEKDAY, ENTERING_DAILY_TIME,
 ENTERING_SPECIAL_DATE, ENTERING_SPECIAL_TIME) = range(8)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_reminders(uid): return load_data().get(str(uid), [])

def add_to_file(uid, reminder):
    data = load_data()
    data.setdefault(str(uid), []).append(reminder)
    save_data(data)

def update_reminder(uid, rid, key, val):
    data = load_data()
    for r in data.get(str(uid), []):
        if r["id"] == rid:
            r[key] = val
    save_data(data)

def remove_reminder(uid, rid):
    data = load_data()
    data[str(uid)] = [r for r in data.get(str(uid), []) if r["id"] != rid]
    save_data(data)

def gen_id():
    import random, string
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=8))

def weekday_uz(n):
    return ["Dushanba","Seshanba","Chorshanba","Payshanba","Juma","Shanba","Yakshanba"][n % 7]

def type_uz(t):
    return {"once":"Bir martalik","daily":"Kundalik","weekly":"Haftalik","special":"Maxsus sana"}.get(t, t)

def msg_reminder(name, title):
    return (
        f"🔔 *Eslatma / Reminder*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Assalomu alaykum, *{name}*!\n\n"
        f"📌 *{title}*\n\n"
        f"🕐 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

def msg_pre(name, title):
    return (
        f"⏰ *15 daqiqadan keyin eslatma!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👋 *{name}*, tayyor bo'ling!\n\n"
        f"📌 *{title}*\n"
        f"━━━━━━━━━━━━━━━━━━━━"
    )

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name
    kb = [
        [InlineKeyboardButton("➕ Eslatma qo'shish", callback_data="add")],
        [InlineKeyboardButton("📋 Eslatmalarim",     callback_data="list")],
        [InlineKeyboardButton("ℹ️ Yordam",           callback_data="help")],
    ]
    text = (
        f"🌟 *Assalomu alaykum, {name}!*\n\n"
        f"Men sizning *Eslatma Botingizman* 🔔\n"
        f"Muhim ishlaringizni unutmaysiz!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👇 Quyidan tanlang:"
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(text, parse_mode="Markdown",
                                                        reply_markup=InlineKeyboardMarkup(kb))
    else:
        await update.message.reply_text(text, parse_mode="Markdown",
                                        reply_markup=InlineKeyboardMarkup(kb))

async def add_reminder(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    kb = [
        [InlineKeyboardButton("⚡ Bir martalik",  callback_data="type_once")],
        [InlineKeyboardButton("🔁 Kundalik",      callback_data="type_daily")],
        [InlineKeyboardButton("📅 Haftalik",      callback_data="type_weekly")],
        [InlineKeyboardButton("🎂 Maxsus sana",   callback_data="type_special")],
        [InlineKeyboardButton("🔙 Orqaga",        callback_data="back_main")],
    ]
    send = query.message.reply_text if query else update.message.reply_text
    await send(
        "📌 *Eslatma turini tanlang:*\n\n"
        "⚡ *Bir martalik* — faqat bir marta\n"
        "🔁 *Kundalik* — har kuni\n"
        "📅 *Haftalik* — haftada bir kun\n"
        "🎂 *Maxsus sana* — tug'ilgan kun, to'lov sanasi",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb),
    )
    return CHOOSING_TYPE

async def choose_type(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["rtype"] = query.data.replace("type_", "")
    await query.message.reply_text(
        "✏️ *Eslatma sarlavhasini yozing:*\n_(masalan: Dori ichish, Uy kiraysi)_",
        parse_mode="Markdown",
    )
    return ENTERING_TITLE

async def enter_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["title"] = update.message.text.strip()
    rtype = ctx.user_data["rtype"]
    if rtype == "once":
        await update.message.reply_text(
            "📅 *Sanani kiriting:*\n`KK.OO.YYYY` formatida\n_(masalan: 25.06.2025)_",
            parse_mode="Markdown")
        return ENTERING_DATE
    elif rtype == "daily":
        await update.message.reply_text(
            "🕐 *Har kuni soat nechada?*\n`SS:MM` formatida\n_(masalan: 08:00)_",
            parse_mode="Markdown")
        return ENTERING_DAILY_TIME
    elif rtype == "weekly":
        kb = [
            [InlineKeyboardButton("Dushanba", callback_data="wd_0"),
             InlineKeyboardButton("Seshanba", callback_data="wd_1")],
            [InlineKeyboardButton("Chorshanba", callback_data="wd_2"),
             InlineKeyboardButton("Payshanba", callback_data="wd_3")],
            [InlineKeyboardButton("Juma", callback_data="wd_4"),
             InlineKeyboardButton("Shanba", callback_data="wd_5")],
            [InlineKeyboardButton("Yakshanba", callback_data="wd_6")],
        ]
        await update.message.reply_text("📅 *Haftaning qaysi kuni?*",
                                         parse_mode="Markdown",
                                         reply_markup=InlineKeyboardMarkup(kb))
        return ENTERING_WEEKDAY
    elif rtype == "special":
        await update.message.reply_text(
            "🎂 *Maxsus sanani kiriting:*\n`KK.OO` formatida\n_(masalan: 15.03)_",
            parse_mode="Markdown")
        return ENTERING_SPECIAL_DATE

async def enter_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%d.%m.%Y")
        ctx.user_data["date"] = update.message.text.strip()
        await update.message.reply_text("🕐 *Soatni kiriting:*\n`SS:MM` formatida", parse_mode="Markdown")
        return ENTERING_TIME
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri! `KK.OO.YYYY` formatida:", parse_mode="Markdown")
        return ENTERING_DATE

async def enter_weekday(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    ctx.user_data["weekday"] = int(query.data.replace("wd_", ""))
    await query.message.reply_text("🕐 *Soatni kiriting:*\n`SS:MM` formatida", parse_mode="Markdown")
    return ENTERING_TIME

async def enter_daily_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%H:%M")
        ctx.user_data["time"] = update.message.text.strip()
        return await save_confirm(update, ctx)
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri! `SS:MM` formatida:", parse_mode="Markdown")
        return ENTERING_DAILY_TIME

async def enter_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%H:%M")
        ctx.user_data["time"] = update.message.text.strip()
        return await save_confirm(update, ctx)
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri! `SS:MM` formatida:", parse_mode="Markdown")
        return ENTERING_TIME

async def enter_special_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        parts = update.message.text.strip().split(".")
        assert len(parts) == 2
        int(parts[0]); int(parts[1])
        ctx.user_data["special_date"] = update.message.text.strip()
        await update.message.reply_text("🕐 *Soatni kiriting:*\n`SS:MM` formatida", parse_mode="Markdown")
        return ENTERING_SPECIAL_TIME
    except Exception:
        await update.message.reply_text("❌ Noto'g'ri! `KK.OO` formatida:", parse_mode="Markdown")
        return ENTERING_SPECIAL_DATE

async def enter_special_time(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        datetime.strptime(update.message.text.strip(), "%H:%M")
        ctx.user_data["time"] = update.message.text.strip()
        return await save_confirm(update, ctx)
    except ValueError:
        await update.message.reply_text("❌ Noto'g'ri! `SS:MM` formatida:", parse_mode="Markdown")
        return ENTERING_SPECIAL_TIME

async def save_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user  = update.effective_user
    uid   = str(user.id)
    rtype = ctx.user_data["rtype"]
    title = ctx.user_data["title"]
    tstr  = ctx.user_data.get("time", "08:00")
    h, m  = map(int, tstr.split(":"))
    rid   = gen_id()

    reminder = {
        "id": rid, "type": rtype, "title": title,
        "time": tstr, "done": False,
        "user_name": user.first_name, "chat_id": user.id,
    }

    scheduler: AsyncIOScheduler = ctx.bot_data["scheduler"]
    app = ctx.application

    if rtype == "once":
        ds = ctx.user_data["date"]
        reminder["date"] = ds
        dt  = datetime.strptime(f"{ds} {tstr}", "%d.%m.%Y %H:%M")
        dtp = dt - timedelta(minutes=15)
        if dt > datetime.now():
            scheduler.add_job(send_reminder, DateTrigger(run_date=dt, timezone=TIMEZONE),
                              args=[app, uid, rid], id=f"{rid}_main")
        if dtp > datetime.now():
            scheduler.add_job(send_pre, DateTrigger(run_date=dtp, timezone=TIMEZONE),
                              args=[app, uid, rid], id=f"{rid}_pre")
        summary = f"📅 {ds} soat {tstr}"
    elif rtype == "daily":
        scheduler.add_job(send_reminder, CronTrigger(hour=h, minute=m, timezone=TIMEZONE),
                          args=[app, uid, rid], id=f"{rid}_main")
        h2, m2 = (h, m - 15) if m >= 15 else (h - 1, m + 45)
        scheduler.add_job(send_pre, CronTrigger(hour=h2 % 24, minute=m2, timezone=TIMEZONE),
                          args=[app, uid, rid], id=f"{rid}_pre")
        summary = f"🔁 Har kuni {tstr}"
    elif rtype == "weekly":
        wd = ctx.user_data.get("weekday", 0)
        reminder["weekday"] = wd
        scheduler.add_job(send_reminder,
                          CronTrigger(day_of_week=wd, hour=h, minute=m, timezone=TIMEZONE),
                          args=[app, uid, rid], id=f"{rid}_main")
        summary = f"📅 Har {weekday_uz(wd)} {tstr}"
    elif rtype == "special":
        sp = ctx.user_data["special_date"]
        reminder["special_date"] = sp
        day, month = map(int, sp.split("."))
        scheduler.add_job(send_reminder,
                          CronTrigger(month=month, day=day, hour=h, minute=m, timezone=TIMEZONE),
                          args=[app, uid, rid], id=f"{rid}_main")
        summary = f"🎂 Har yil {sp} soat {tstr}"
    else:
        summary = ""

    add_to_file(uid, reminder)
    await update.message.reply_text(
        f"✅ *Eslatma saqlandi!*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *{title}*\n"
        f"🗂 {type_uz(rtype)}\n"
        f"⏰ {summary}\n"
        f"🔔 15 daqiqa oldin ogohlantirish: ✅\n"
        f"━━━━━━━━━━━━━━━━━━━━",
        parse_mode="Markdown",
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def send_reminder(app, uid, rid):
    r = next((x for x in get_reminders(uid) if x["id"] == rid), None)
    if not r or r.get("done"): return
    kb = [[InlineKeyboardButton("✅ Bajarildi", callback_data=f"done_{rid}"),
           InlineKeyboardButton("🗑 O'chirish",  callback_data=f"del_{rid}")]]
    await app.bot.send_message(r["chat_id"], msg_reminder(r["user_name"], r["title"]),
                               parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def send_pre(app, uid, rid):
    r = next((x for x in get_reminders(uid) if x["id"] == rid), None)
    if not r or r.get("done"): return
    await app.bot.send_message(r["chat_id"], msg_pre(r["user_name"], r["title"]),
                               parse_mode="Markdown")

async def list_reminders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query: await query.answer()
    uid  = str(update.effective_user.id)
    name = update.effective_user.first_name
    send = query.message.reply_text if query else update.message.reply_text
    active = [r for r in get_reminders(uid) if not r.get("done")]
    if not active:
        await send(f"👋 *{name}*, hozircha eslatmalar yo'q.\n➕ /add — yangi qo'shing!", parse_mode="Markdown")
        return
    text = f"📋 *{name}ning eslatmalari:*\n━━━━━━━━━━━━━━━━━━━━\n\n"
    kb   = []
    for i, r in enumerate(active, 1):
        extra = (f"{r.get('date','')} " if r["type"]=="once"
                 else f"{weekday_uz(r.get('weekday',0))} " if r["type"]=="weekly"
                 else f"{r.get('special_date','')} " if r["type"]=="special" else "")
        text += f"*{i}. {r['title']}*\n   🗂 {type_uz(r['type'])} | ⏰ {extra}{r.get('time','')}\n\n"
        kb.append([InlineKeyboardButton(f"✅ {r['title'][:20]}", callback_data=f"done_{r['id']}"),
                   InlineKeyboardButton("🗑", callback_data=f"del_{r['id']}")])
    kb.append([InlineKeyboardButton("➕ Yangi eslatma", callback_data="add")])
    await send(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(kb))

async def buttons(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid  = str(update.effective_user.id)
    name = update.effective_user.first_name
    if data == "back_main": return await start(update, ctx)
    if data == "list":      return await list_reminders(update, ctx)
    if data == "help":
        await query.message.reply_text(
            "ℹ️ *Yordam*\n━━━━━━━━━━━━━━━━━━━━\n"
            "/start — Bosh menyu\n/add — Yangi eslatma\n/list — Ro'yxat\n\n"
            "🔔 *Turlar:*\n⚡ Bir martalik\n🔁 Kundalik\n📅 Haftalik\n🎂 Maxsus sana\n\n"
            "⏰ Har eslatmadan *15 daqiqa oldin* ogohlantirish!\n━━━━━━━━━━━━━━━━━━━━",
            parse_mode="Markdown")
        return
    if data.startswith("done_"):
        rid = data[5:]
        update_reminder(uid, rid, "done", True)
        scheduler: AsyncIOScheduler = ctx.bot_data["scheduler"]
        for jid in [f"{rid}_main", f"{rid}_pre"]:
            if scheduler.get_job(jid): scheduler.remove_job(jid)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"✅ *Bajarildi!* Zo'r, *{name}*! 👏", parse_mode="Markdown")
        return
    if data.startswith("del_"):
        rid = data[4:]
        remove_reminder(uid, rid)
        scheduler: AsyncIOScheduler = ctx.bot_data["scheduler"]
        for jid in [f"{rid}_main", f"{rid}_pre"]:
            if scheduler.get_job(jid): scheduler.remove_job(jid)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("🗑 *Eslatma o'chirildi.*", parse_mode="Markdown")

def restore_jobs(scheduler, app):
    now = datetime.now()
    for uid, reminders in load_data().items():
        for r in reminders:
            if r.get("done"): continue
            rid  = r["id"]; rtype = r["type"]
            tstr = r.get("time", "08:00")
            h, m = map(int, tstr.split(":"))
            try:
                if rtype == "once":
                    dt = datetime.strptime(f"{r['date']} {tstr}", "%d.%m.%Y %H:%M")
                    if dt > now:
                        scheduler.add_job(send_reminder, DateTrigger(run_date=dt, timezone=TIMEZONE),
                                          args=[app, uid, rid], id=f"{rid}_main")
                    dtp = dt - timedelta(minutes=15)
                    if dtp > now:
                        scheduler.add_job(send_pre, DateTrigger(run_date=dtp, timezone=TIMEZONE),
                                          args=[app, uid, rid], id=f"{rid}_pre")
                elif rtype == "daily":
                    scheduler.add_job(send_reminder, CronTrigger(hour=h, minute=m, timezone=TIMEZONE),
                                      args=[app, uid, rid], id=f"{rid}_main")
                    h2, m2 = (h, m-15) if m >= 15 else (h-1, m+45)
                    scheduler.add_job(send_pre, CronTrigger(hour=h2 % 24, minute=m2, timezone=TIMEZONE),
                                      args=[app, uid, rid], id=f"{rid}_pre")
                elif rtype == "weekly":
                    wd = r.get("weekday", 0)
                    scheduler.add_job(send_reminder,
                                      CronTrigger(day_of_week=wd, hour=h, minute=m, timezone=TIMEZONE),
                                      args=[app, uid, rid], id=f"{rid}_main")
                elif rtype == "special":
                    d2, mo = map(int, r.get("special_date","1.1").split("."))
                    scheduler.add_job(send_reminder,
                                      CronTrigger(month=mo, day=d2, hour=h, minute=m, timezone=TIMEZONE),
                                      args=[app, uid, rid], id=f"{rid}_main")
            except Exception as e:
                logger.warning(f"Restore xato {rid}: {e}")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    app.bot_data["scheduler"] = scheduler

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_reminder, pattern="^add$"),
                      CommandHandler("add", add_reminder)],
        states={
            CHOOSING_TYPE:        [CallbackQueryHandler(choose_type, pattern="^type_")],
            ENTERING_TITLE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_title)],
            ENTERING_DATE:        [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_date)],
            ENTERING_TIME:        [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_time),
                                   CallbackQueryHandler(enter_weekday, pattern="^wd_")],
            ENTERING_WEEKDAY:     [CallbackQueryHandler(enter_weekday, pattern="^wd_")],
            ENTERING_DAILY_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_daily_time)],
            ENTERING_SPECIAL_DATE:[MessageHandler(filters.TEXT & ~filters.COMMAND, enter_special_date)],
            ENTERING_SPECIAL_TIME:[MessageHandler(filters.TEXT & ~filters.COMMAND, enter_special_time)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list",  list_reminders))
    app.add_handler(CommandHandler("add",   add_reminder))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(buttons))

    async def on_start(app):
        restore_jobs(scheduler, app)
        scheduler.start()
        logger.info("✅ Bot ishga tushdi!")

    app.post_init = on_start
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
