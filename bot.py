# bot.py
import json
import os
from math import ceil
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

DATA_FILE = "data.json"
BOT_TOKEN = os.environ.get("BOT_TOKEN")  # поставь токен как переменную окружения

# --- утилиты ---
def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# Делим длинный текст на страницы примерно по chars_per_page символов (попробуй 1500-2500)
def paginate_text(text, chars_per_page=1800):
    pages = []
    i = 0
    while i < len(text):
        cut = i + chars_per_page
        # постараемся резать по переносу строки/точке для удобочитаемости
        if cut < len(text):
            # ищем ближайшую точку или перенос строки перед cut
            j = text.rfind("\n", i, cut)
            if j == -1:
                j = text.rfind(". ", i, cut)
            if j == -1:
                j = cut
            else:
                j += 1
            pages.append(text[i:j].strip())
            i = j
        else:
            pages.append(text[i:].strip())
            break
    return pages

# Русский алфавит (верхний регистр)
RUS_ALPHABET = list("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ")

# --- обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    kb = []
    row = []
    for key, v in data.items():
        row.append(InlineKeyboardButton(v.get("display_name", key), callback_data=f"thinker:{key}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("О боте", callback_data="about")])
    text = "📚 <b>Книга мыслителей</b>\n\nВыбери мыслителя:"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

async def about_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("Бот-«книга». Выбирай мыслителя и читай биографию и глоссарий. Сделано для учебы.")

async def thinker_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = load_data()
    _, thinker_key = update.callback_query.data.split(":")
    thinker = data.get(thinker_key)
    if not thinker:
        await update.callback_query.edit_message_text("Не найден мыслитель.")
        return

    bio = thinker.get("bio", "Биография отсутствует.")
    pages = paginate_text(bio)
    # сохраняем временное состояние в user_data: current view
    context.user_data["view"] = {"type": "bio", "thinker": thinker_key, "page": 0, "pages_count": len(pages)}
    # клавиатура: назад/вперёд, глоссарий, назад в список
    kb = []
    nav_row = []
    if len(pages) > 1:
        nav_row.append(InlineKeyboardButton("« Назад", callback_data="bio_nav:prev"))
        nav_row.append(InlineKeyboardButton("Вперёд »", callback_data="bio_nav:next"))
        kb.append(nav_row)
    kb.append([InlineKeyboardButton("Глоссарий", callback_data=f"gloss_letters:{thinker_key}")])
    kb.append([InlineKeyboardButton("В список мыслителей", callback_data="to_list")])

    await update.callback_query.edit_message_text(f"<b>{thinker.get('display_name')}</b>\n\n{pages[0]}\n\n(<i>Страница 1/{len(pages)}</i>)",
                                                 parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def bio_nav_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    user_view = context.user_data.get("view")
    if not user_view or user_view.get("type") != "bio":
        await update.callback_query.edit_message_text("Время вышло, выбери мыслителя заново: /start")
        return
    data = load_data()
    thinker_key = user_view["thinker"]
    bio = data[thinker_key].get("bio", "")
    pages = paginate_text(bio)
    page = user_view["page"]
    if update.callback_query.data.endswith("next"):
        page = min(page + 1, len(pages) - 1)
    else:
        page = max(0, page - 1)
    user_view["page"] = page
    context.user_data["view"] = user_view

    kb = []
    if len(pages) > 1:
        kb.append([
            InlineKeyboardButton("« Назад", callback_data="bio_nav:prev"),
            InlineKeyboardButton("Вперёд »", callback_data="bio_nav:next")
        ])
    kb.append([InlineKeyboardButton("Глоссарий", callback_data=f"gloss_letters:{thinker_key}")])
    kb.append([InlineKeyboardButton("В список мыслителей", callback_data="to_list")])

    await update.callback_query.edit_message_text(f"<b>{data[thinker_key].get('display_name')}</b>\n\n{pages[page]}\n\n(<i>Страница {page+1}/{len(pages)}</i>)",
                                                 parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def to_list_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    # просто показать стартовое меню
    data = load_data()
    kb = []
    row = []
    for key, v in data.items():
        row.append(InlineKeyboardButton(v.get("display_name", key), callback_data=f"thinker:{key}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("О боте", callback_data="about")])
    await update.callback_query.edit_message_text("📚 <b>Книга мыслителей</b>\n\nВыбери мыслителя:", parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def gloss_letters_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, thinker_key = update.callback_query.data.split(":")
    data = load_data()
    gloss = data[thinker_key].get("glossary", {})
    # получаем буквы, по которым есть термины, в порядке алфавита
    available = sorted(list(gloss.keys()), key=lambda ch: RUS_ALPHABET.index(ch) if ch in RUS_ALPHABET else 999)
    # build keyboard — буквы в несколько рядов
    kb = []
    row = []
    for i, ch in enumerate(available):
        row.append(InlineKeyboardButton(ch, callback_data=f"gloss_terms:{thinker_key}:{ch}"))
        if len(row) == 7:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton("Назад в биографию", callback_data=f"thinker:{thinker_key}")])
    kb.append([InlineKeyboardButton("В список мыслителей", callback_data="to_list")])
    await update.callback_query.edit_message_text(f"📖 <b>Глоссарий — {data[thinker_key].get('display_name')}</b>\n\nВыберите букву:",
                                                 parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

async def gloss_terms_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    _, thinker_key, letter = update.callback_query.data.split(":")
    data = load_data()
    terms = data[thinker_key].get("glossary", {}).get(letter, [])
    if not terms:
        await update.callback_query.edit_message_text("Термины на эту букву не найдены.")
        return
    # формируем текст со списком терминов
    text_parts = [f"📚 <b>Глоссарий — {data[thinker_key].get('display_name')}</b>",
                  f"<b>Буква {letter}</b> — найдено {len(terms)} терминов:\n"]
    for t in terms:
        text_parts.append(f"• <b>{t.get('term')}</b>\n{t.get('definition')}\n")
    text = "\n".join(text_parts)
    kb = [
        [InlineKeyboardButton("← К буквам", callback_data=f"gloss_letters:{thinker_key}")],
        [InlineKeyboardButton("В биографию", callback_data=f"thinker:{thinker_key}"),
         InlineKeyboardButton("В список мыслителей", callback_data="to_list")]
    ]
    await update.callback_query.edit_message_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(kb))

# --- регистрация обработчиков ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(about_cb, pattern="^about$"))
    app.add_handler(CallbackQueryHandler(thinker_cb, pattern="^thinker:"))
    app.add_handler(CallbackQueryHandler(bio_nav_cb, pattern="^bio_nav:"))
    app.add_handler(CallbackQueryHandler(to_list_cb, pattern="^to_list$"))
    app.add_handler(CallbackQueryHandler(gloss_letters_cb, pattern="^gloss_letters:"))
    app.add_handler(CallbackQueryHandler(gloss_terms_cb, pattern="^gloss_terms:"))

    print("Bot started")
    app.run_polling()

if __name__ == "__main__":
    main()
