import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = os.getenv("DB_PATH", "zyveron.db")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is required")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID environment variable is required")

logging.basicConfig(level=logging.INFO)

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.executescript('''
CREATE TABLE IF NOT EXISTS users (
    tg_id INTEGER PRIMARY KEY,
    username TEXT,
    full_name TEXT,
    lang TEXT DEFAULT 'ru',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER NOT NULL,
    username TEXT,
    name TEXT,
    lang TEXT,
    service TEXT,
    description TEXT,
    budget TEXT,
    contact TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    photo_file_id TEXT NOT NULL,
    caption_ru TEXT DEFAULT '',
    caption_lv TEXT DEFAULT '',
    caption_en TEXT DEFAULT '',
    created_at TEXT NOT NULL
);
''')
conn.commit()

TEXT = {
    'ru': {
        'choose': '🌐 <b>Выберите язык</b>',
        'welcome': '👋 Добро пожаловать в <b>ZYVERON</b>!\n\nЦифровые решения для бизнеса: Telegram-боты, автоматизация, сайты и индивидуальная разработка.\n\nВыберите раздел:',
        'services': '🛠 <b>Наши услуги</b>\n\n🤖 Telegram-боты\n⚙️ Автоматизация бизнеса\n🌐 Сайты и лендинги\n📢 Telegram-инструменты и продвижение\n🧩 Индивидуальные IT-решения',
        'prices': '💰 <b>Стартовые цены</b>\n\n🤖 Telegram-бот — от €50\n📦 Бот для заказов — от €100\n⚙️ Автоматизация — от €75\n🌐 Сайт/лендинг — от €100\n🛠 Поддержка — от €10/мес.\n\nТочная стоимость зависит от задачи и функций.',
        'portfolio_empty': '🎨 <b>Портфолио</b>\n\nПока здесь нет опубликованных работ. Мы добавим первые проекты совсем скоро.',
        'order_start': '📝 <b>Новая заявка</b>\n\nВыберите, что вам нужно:',
        'ask_desc': '✏️ Опишите задачу своими словами. Чем подробнее — тем точнее мы сможем оценить проект.',
        'ask_budget': '💶 Какой бюджет вы ориентировочно рассматриваете?\n\nМожно написать «не знаю», если хотите получить наше предложение.',
        'ask_contact': '📞 Как с вами связаться?\n\nМожно оставить Telegram username, телефон или написать «здесь».',
        'request_done': '✅ <b>Заявка отправлена!</b>\n\nСпасибо. ZYVERON получил вашу заявку и свяжется с вами после ознакомления.',
        'contact': '💬 <b>Связаться с ZYVERON</b>\n\nНапишите нам здесь или используйте контакт, указанный в нашем канале.',
        'cancel': '❌ Заявка отменена.',
        'back': '⬅️ Назад', 'home': '🏠 Главное меню', 'lang': '🌐 Язык',
        'order': '📝 Заказать', 'portfolio': '🎨 Портфолио', 'prices_btn': '💰 Цены', 'services_btn': '🛠 Услуги', 'contact_btn': '💬 Связаться',
        'service_bot': '🤖 Telegram-бот', 'service_auto': '⚙️ Автоматизация', 'service_site': '🌐 Сайт/лендинг', 'service_other': '🧩 Другое',
        'cancel_btn': '❌ Отмена', 'next': '➡️ Далее',
        'admin_title': '🔐 <b>Админ-панель ZYVERON</b>', 'admin_requests': '📥 Заявки', 'admin_stats': '📊 Статистика', 'admin_portfolio': '🎨 Добавить в портфолио',
        'admin_no_requests': '📭 Новых заявок нет.', 'admin_wait_photo': '📸 Отправьте фотографию проекта одним сообщением. Она будет добавлена в портфолио.',
        'admin_photo_saved': '✅ Фото добавлено в портфолио.', 'admin_bad': '❌ Команда доступна только администратору.',
    },
    'lv': {
        'choose': '🌐 <b>Izvēlieties valodu</b>',
        'welcome': '👋 Laipni lūdzam <b>ZYVERON</b>!\n\nDigitālie risinājumi biznesam: Telegram boti, automatizācija, mājaslapas un individuāla izstrāde.\n\nIzvēlieties sadaļu:',
        'services': '🛠 <b>Mūsu pakalpojumi</b>\n\n🤖 Telegram boti\n⚙️ Biznesa automatizācija\n🌐 Mājaslapas un landing lapas\n📢 Telegram rīki un reklāma\n🧩 Individuāli IT risinājumi',
        'prices': '💰 <b>Sākuma cenas</b>\n\n🤖 Telegram bots — no €50\n📦 Pasūtījumu bots — no €100\n⚙️ Automatizācija — no €75\n🌐 Mājaslapa/landing — no €100\n🛠 Atbalsts — no €10/mēn.\n\nPrecīza cena atkarīga no uzdevuma un funkcijām.',
        'portfolio_empty': '🎨 <b>Portfolio</b>\n\nŠeit vēl nav publicētu darbu. Pirmos projektus pievienosim drīzumā.',
        'order_start': '📝 <b>Jauns pieteikums</b>\n\nIzvēlieties nepieciešamo:',
        'ask_desc': '✏️ Aprakstiet uzdevumu saviem vārdiem. Jo vairāk detaļu, jo precīzāk varēsim novērtēt projektu.',
        'ask_budget': '💶 Kādu budžetu aptuveni plānojat?\n\nVarat rakstīt “nezinu”, ja vēlaties saņemt mūsu piedāvājumu.',
        'ask_contact': '📞 Kā ar jums sazināties?\n\nVarat norādīt Telegram username, tālruni vai rakstīt “šeit”.',
        'request_done': '✅ <b>Pieteikums nosūtīts!</b>\n\nPaldies. ZYVERON ir saņēmis jūsu pieteikumu un sazināsies ar jums.',
        'contact': '💬 <b>Sazināties ar ZYVERON</b>\n\nRakstiet mums šeit vai izmantojiet mūsu kanālā norādīto kontaktu.',
        'cancel': '❌ Pieteikums atcelts.',
        'back': '⬅️ Atpakaļ', 'home': '🏠 Galvenā izvēlne', 'lang': '🌐 Valoda',
        'order': '📝 Pasūtīt', 'portfolio': '🎨 Portfolio', 'prices_btn': '💰 Cenas', 'services_btn': '🛠 Pakalpojumi', 'contact_btn': '💬 Sazināties',
        'service_bot': '🤖 Telegram bots', 'service_auto': '⚙️ Automatizācija', 'service_site': '🌐 Mājaslapa/landing', 'service_other': '🧩 Cits',
        'cancel_btn': '❌ Atcelt', 'next': '➡️ Tālāk',
        'admin_title': '🔐 <b>ZYVERON administratora panelis</b>', 'admin_requests': '📥 Pieteikumi', 'admin_stats': '📊 Statistika', 'admin_portfolio': '🎨 Pievienot portfolio',
        'admin_no_requests': '📭 Jaunu pieteikumu nav.', 'admin_wait_photo': '📸 Nosūtiet projekta foto vienā ziņā. Tas tiks pievienots portfolio.',
        'admin_photo_saved': '✅ Foto pievienots portfolio.', 'admin_bad': '❌ Šī komanda pieejama tikai administratoram.',
    },
    'en': {
        'choose': '🌐 <b>Choose your language</b>',
        'welcome': '👋 Welcome to <b>ZYVERON</b>!\n\nDigital solutions for business: Telegram bots, automation, websites and custom development.\n\nChoose a section:',
        'services': '🛠 <b>Our services</b>\n\n🤖 Telegram bots\n⚙️ Business automation\n🌐 Websites and landing pages\n📢 Telegram tools and promotion\n🧩 Custom IT solutions',
        'prices': '💰 <b>Starting prices</b>\n\n🤖 Telegram bot — from €50\n📦 Ordering bot — from €100\n⚙️ Automation — from €75\n🌐 Website/landing — from €100\n🛠 Support — from €10/month\n\nThe final price depends on the task and features.',
        'portfolio_empty': '🎨 <b>Portfolio</b>\n\nThere are no published projects here yet. We will add our first projects soon.',
        'order_start': '📝 <b>New request</b>\n\nChoose what you need:',
        'ask_desc': '✏️ Describe your task in your own words. More details help us estimate the project more accurately.',
        'ask_budget': '💶 What approximate budget are you considering?\n\nYou can write “I don’t know” if you want us to make an offer.',
        'ask_contact': '📞 How can we contact you?\n\nLeave a Telegram username, phone number, or write “here”.',
        'request_done': '✅ <b>Request sent!</b>\n\nThank you. ZYVERON has received your request and will contact you after reviewing it.',
        'contact': '💬 <b>Contact ZYVERON</b>\n\nWrite to us here or use the contact listed in our channel.',
        'cancel': '❌ Request cancelled.',
        'back': '⬅️ Back', 'home': '🏠 Main menu', 'lang': '🌐 Language',
        'order': '📝 Order', 'portfolio': '🎨 Portfolio', 'prices_btn': '💰 Prices', 'services_btn': '🛠 Services', 'contact_btn': '💬 Contact',
        'service_bot': '🤖 Telegram bot', 'service_auto': '⚙️ Automation', 'service_site': '🌐 Website/landing', 'service_other': '🧩 Other',
        'cancel_btn': '❌ Cancel', 'next': '➡️ Next',
        'admin_title': '🔐 <b>ZYVERON admin panel</b>', 'admin_requests': '📥 Requests', 'admin_stats': '📊 Statistics', 'admin_portfolio': '🎨 Add to portfolio',
        'admin_no_requests': '📭 No new requests.', 'admin_wait_photo': '📸 Send a project photo in one message. It will be added to the portfolio.',
        'admin_photo_saved': '✅ Photo added to portfolio.', 'admin_bad': '❌ This command is available only to the administrator.',
    }
}

class OrderForm(StatesGroup):
    service = State()
    description = State()
    budget = State()
    contact = State()

class AdminForm(StatesGroup):
    portfolio_photo = State()


def lang_of(tg_id: int) -> str:
    row = conn.execute('SELECT lang FROM users WHERE tg_id=?', (tg_id,)).fetchone()
    return row['lang'] if row and row['lang'] in TEXT else 'ru'


def save_user(message: Message, lang=None):
    current = lang or lang_of(message.from_user.id)
    conn.execute('''INSERT INTO users(tg_id, username, full_name, lang, created_at)
                    VALUES(?,?,?,?,?)
                    ON CONFLICT(tg_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name''',
                 (message.from_user.id, message.from_user.username, message.from_user.full_name, current, datetime.utcnow().isoformat()))
    conn.commit()


def set_lang(tg_id: int, lang: str):
    conn.execute('UPDATE users SET lang=? WHERE tg_id=?', (lang, tg_id))
    conn.commit()


def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🇷🇺 Русский', callback_data='lang:ru')],
        [InlineKeyboardButton(text='🇱🇻 Latviešu', callback_data='lang:lv')],
        [InlineKeyboardButton(text='🇬🇧 English', callback_data='lang:en')],
    ])


def main_keyboard(l: str):
    t = TEXT[l]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['services_btn'], callback_data='menu:services'), InlineKeyboardButton(text=t['prices_btn'], callback_data='menu:prices')],
        [InlineKeyboardButton(text=t['portfolio'], callback_data='menu:portfolio')],
        [InlineKeyboardButton(text=t['order'], callback_data='menu:order')],
        [InlineKeyboardButton(text=t['contact_btn'], callback_data='menu:contact'), InlineKeyboardButton(text=t['lang'], callback_data='menu:lang')],
    ])


def back_keyboard(l: str):
    t = TEXT[l]
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t['home'], callback_data='menu:home')]])


def service_keyboard(l: str):
    t = TEXT[l]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['service_bot'], callback_data='order_service:bot')],
        [InlineKeyboardButton(text=t['service_auto'], callback_data='order_service:auto')],
        [InlineKeyboardButton(text=t['service_site'], callback_data='order_service:site')],
        [InlineKeyboardButton(text=t['service_other'], callback_data='order_service:other')],
        [InlineKeyboardButton(text=t['cancel_btn'], callback_data='order_cancel')],
    ])


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📥 Заявки', callback_data='admin:requests'), InlineKeyboardButton(text='📊 Статистика', callback_data='admin:stats')],
        [InlineKeyboardButton(text='🎨 Добавить в портфолио', callback_data='admin:add_portfolio')],
    ])


def service_name(code: str, l: str):
    return {'bot': TEXT[l]['service_bot'], 'auto': TEXT[l]['service_auto'], 'site': TEXT[l]['service_site'], 'other': TEXT[l]['service_other']}.get(code, code)

async def show_home(message: Message, l: str):
    await message.answer(TEXT[l]['welcome'], reply_markup=main_keyboard(l))

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    save_user(message)
    await message.answer(TEXT['ru']['choose'], reply_markup=lang_keyboard())

@dp.callback_query(F.data.startswith('lang:'))
async def choose_lang(call: CallbackQuery):
    l = call.data.split(':', 1)[1]
    set_lang(call.from_user.id, l)
    await call.message.edit_text(TEXT[l]['welcome'], reply_markup=main_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:lang')
async def change_lang(call: CallbackQuery):
    await call.message.edit_text(TEXT[lang_of(call.from_user.id)]['choose'], reply_markup=lang_keyboard())
    await call.answer()

@dp.callback_query(F.data == 'menu:home')
async def menu_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    l = lang_of(call.from_user.id)
    await call.message.edit_text(TEXT[l]['welcome'], reply_markup=main_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:services')
async def menu_services(call: CallbackQuery):
    l = lang_of(call.from_user.id)
    await call.message.edit_text(TEXT[l]['services'], reply_markup=back_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:prices')
async def menu_prices(call: CallbackQuery):
    l = lang_of(call.from_user.id)
    await call.message.edit_text(TEXT[l]['prices'], reply_markup=back_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:contact')
async def menu_contact(call: CallbackQuery):
    l = lang_of(call.from_user.id)
    await call.message.edit_text(TEXT[l]['contact'], reply_markup=back_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:portfolio')
async def menu_portfolio(call: CallbackQuery):
    l = lang_of(call.from_user.id)
    rows = conn.execute('SELECT * FROM portfolio ORDER BY id DESC LIMIT 10').fetchall()
    if not rows:
        await call.message.edit_text(TEXT[l]['portfolio_empty'], reply_markup=back_keyboard(l))
    else:
        await call.message.delete()
        for row in rows:
            caption = row[f'caption_{l}'] or ''
            await call.message.answer_photo(row['photo_file_id'], caption=caption)
        await call.message.answer(TEXT[l]['portfolio_empty'].split('\n\n')[0], reply_markup=back_keyboard(l))
    await call.answer()

@dp.callback_query(F.data == 'menu:order')
async def menu_order(call: CallbackQuery, state: FSMContext):
    l = lang_of(call.from_user.id)
    await state.set_state(OrderForm.service)
    await call.message.edit_text(TEXT[l]['order_start'], reply_markup=service_keyboard(l))
    await call.answer()

@dp.callback_query(F.data.startswith('order_service:'))
async def order_service(call: CallbackQuery, state: FSMContext):
    l = lang_of(call.from_user.id)
    code = call.data.split(':', 1)[1]
    await state.update_data(service=service_name(code, l))
    await state.set_state(OrderForm.description)
    await call.message.edit_text(TEXT[l]['ask_desc'], reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=TEXT[l]['cancel_btn'], callback_data='order_cancel')]]))
    await call.answer()

@dp.message(OrderForm.description)
async def order_description(message: Message, state: FSMContext):
    l = lang_of(message.from_user.id)
    await state.update_data(description=message.text or '')
    await state.set_state(OrderForm.budget)
    await message.answer(TEXT[l]['ask_budget'])

@dp.message(OrderForm.budget)
async def order_budget(message: Message, state: FSMContext):
    l = lang_of(message.from_user.id)
    await state.update_data(budget=message.text or '')
    await state.set_state(OrderForm.contact)
    await message.answer(TEXT[l]['ask_contact'])

@dp.message(OrderForm.contact)
async def order_contact(message: Message, state: FSMContext):
    l = lang_of(message.from_user.id)
    data = await state.get_data()
    username = message.from_user.username or ''
    conn.execute('''INSERT INTO requests(tg_id, username, name, lang, service, description, budget, contact, created_at)
                    VALUES(?,?,?,?,?,?,?,?,?)''',
                 (message.from_user.id, username, message.from_user.full_name, l, data.get('service',''), data.get('description',''), data.get('budget',''), message.text or '', datetime.utcnow().isoformat()))
    req_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.commit()
    await state.clear()
    await message.answer(TEXT[l]['request_done'], reply_markup=main_keyboard(l))
    admin_text = (
        f"🆕 <b>Новая заявка #{req_id}</b>\n\n"
        f"👤 {escape(message.from_user.full_name)}\n"
        f"🆔 <code>{message.from_user.id}</code>\n"
        f"💬 @{escape(username) if username else 'нет username'}\n"
        f"🌐 {l}\n"
        f"🛠 {escape(data.get('service',''))}\n"
        f"✏️ {escape(data.get('description',''))}\n"
        f"💶 {escape(data.get('budget',''))}\n"
        f"📞 {escape(message.text or '')}"
    )
    try:
        await bot.send_message(ADMIN_ID, admin_text)
    except Exception:
        logging.exception('Failed to notify admin')

@dp.callback_query(F.data == 'order_cancel')
async def order_cancel(call: CallbackQuery, state: FSMContext):
    l = lang_of(call.from_user.id)
    await state.clear()
    await call.message.edit_text(TEXT[l]['cancel'], reply_markup=main_keyboard(l))
    await call.answer()

@dp.message(Command('admin'))
async def admin_command(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(TEXT[lang_of(message.from_user.id)]['admin_bad'])
        return
    await message.answer(TEXT['ru']['admin_title'], reply_markup=admin_keyboard())

@dp.callback_query(F.data == 'admin:stats')
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer('Access denied', show_alert=True); return
    users = conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c']
    requests = conn.execute('SELECT COUNT(*) c FROM requests').fetchone()['c']
    new = conn.execute("SELECT COUNT(*) c FROM requests WHERE status='new'").fetchone()['c']
    portfolio = conn.execute('SELECT COUNT(*) c FROM portfolio').fetchone()['c']
    await call.message.edit_text(f"📊 <b>ZYVERON statistics</b>\n\n👥 Users: {users}\n📥 Requests: {requests}\n🆕 New: {new}\n🎨 Portfolio items: {portfolio}", reply_markup=admin_keyboard())
    await call.answer()

@dp.callback_query(F.data == 'admin:requests')
async def admin_requests(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer('Access denied', show_alert=True); return
    rows = conn.execute("SELECT * FROM requests WHERE status='new' ORDER BY id DESC LIMIT 10").fetchall()
    if not rows:
        await call.message.edit_text(TEXT['ru']['admin_no_requests'], reply_markup=admin_keyboard())
        await call.answer(); return
    lines = ['📥 <b>Новые заявки</b>\n']
    for r in rows:
        lines.append(f"<b>#{r['id']}</b> — {escape(r['service'])}\n👤 {escape(r['name'])}\n💶 {escape(r['budget'])}\n🕒 {r['created_at'][:16]}\n")
    await call.message.edit_text('\n'.join(lines), reply_markup=admin_keyboard())
    await call.answer()

@dp.callback_query(F.data == 'admin:add_portfolio')
async def admin_add_portfolio(call: CallbackQuery, state: FSMContext):
    if call.from_user.id != ADMIN_ID:
        await call.answer('Access denied', show_alert=True); return
    await state.set_state(AdminForm.portfolio_photo)
    await call.message.edit_text(TEXT['ru']['admin_wait_photo'])
    await call.answer()

@dp.message(AdminForm.portfolio_photo, F.photo)
async def admin_portfolio_photo(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    photo_id = message.photo[-1].file_id
    caption = message.caption or ''
    conn.execute('INSERT INTO portfolio(photo_file_id, caption_ru, caption_lv, caption_en, created_at) VALUES(?,?,?,?,?)', (photo_id, caption, caption, caption, datetime.utcnow().isoformat()))
    conn.commit()
    await state.clear()
    await message.answer(TEXT['ru']['admin_photo_saved'], reply_markup=admin_keyboard())

@dp.message(AdminForm.portfolio_photo)
async def admin_portfolio_bad(message: Message):
    await message.answer('📸 Нужна именно фотография. Отправьте фото одним сообщением.')

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
