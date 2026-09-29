
import os, asyncio, logging, sqlite3, json
from pathlib import Path
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv("BOT_TOKEN")
ADMIN_ID=int(os.getenv("ADMIN_ID","0"))
DB_PATH=os.getenv("DB_PATH","/data/zyveron.db")
LOGO_PATH=os.getenv("LOGO_PATH","logo.jpg")
if not TOKEN: raise RuntimeError("BOT_TOKEN is not set")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(LOGO_PATH).parent.mkdir(parents=True, exist_ok=True)

bot=Bot(TOKEN); dp=Dispatcher(storage=MemoryStorage())
conn=sqlite3.connect(DB_PATH, check_same_thread=False); conn.row_factory=sqlite3.Row
cur=conn.cursor()
cur.executescript("""
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, lang TEXT, name TEXT, username TEXT);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, name_ru TEXT, name_lv TEXT, name_en TEXT, desc_ru TEXT, desc_lv TEXT, desc_en TEXT, price_ru TEXT, price_lv TEXT, price_en TEXT, active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT UNIQUE, label_ru TEXT, label_lv TEXT, label_en TEXT, action TEXT, active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS portfolio(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, title_ru TEXT, title_lv TEXT, title_en TEXT, desc_ru TEXT, desc_lv TEXT, desc_en TEXT, active INTEGER DEFAULT 1, sort INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, kind TEXT, service TEXT, budget TEXT, contact TEXT, text TEXT, status TEXT DEFAULT 'new', created TEXT DEFAULT CURRENT_TIMESTAMP);
""")
defaults={
'welcome_ru':"👋 Добро пожаловать в <b>ZYVERON</b>!\n\nЦифровые решения для бизнеса: Telegram-боты, автоматизация, сайты и разработка.",
'welcome_lv':"👋 Laipni lūdzam <b>ZYVERON</b>!\n\nDigitālie risinājumi uzņēmumiem: Telegram roboti, automatizācija, mājaslapas un izstrāde.",
'welcome_en':"👋 Welcome to <b>ZYVERON</b>!\n\nDigital solutions for businesses: Telegram bots, automation, websites and development.",
'ack_ru':"✅ <b>Спасибо! Ваша заявка принята.</b>\nМы получили ваше сообщение и ответим на него как можно скорее.",
'ack_lv':"✅ <b>Paldies! Jūsu pieteikums ir saņemts.</b>\nMēs to izskatīsim un atbildēsim pēc iespējas ātrāk.",
'ack_en':"✅ <b>Thank you! Your request has been received.</b>\nWe will review it and get back to you as soon as possible.",
'contact_ru':"💬 <b>Связаться с ZYVERON</b>\n\nНапишите ваше сообщение одним сообщением.",
'contact_lv':"💬 <b>Sazināties ar ZYVERON</b>\n\nNosūtiet savu ziņu vienā ziņā.",
'contact_en':"💬 <b>Contact ZYVERON</b>\n\nSend your message in one message."
}
for k,v in defaults.items(): cur.execute("INSERT OR IGNORE INTO settings VALUES(?,?)",(k,v))
menu_defaults=[
('services','🛠 Услуги','🛠 Pakalpojumi','🛠 Services','services',1,1),
('prices','💰 Цены','💰 Cenas','💰 Prices','prices',1,2),
('portfolio','🖼 Портфолио','🖼 Portfolio','🖼 Portfolio','portfolio',1,3),
('order','📝 Заказать','📝 Pasūtīt','📝 Order','order',1,4),
('contact','📞 Связаться','📞 Sazināties','📞 Contact','contact',1,5),
('language','🌐 Язык','🌐 Valoda','🌐 Language','language',1,6)]
for x in menu_defaults: cur.execute("INSERT OR IGNORE INTO menu(key,label_ru,label_lv,label_en,action,active,sort) VALUES(?,?,?,?,?,?,?)",x)
conn.commit()

def setting(k): return cur.execute("SELECT v FROM settings WHERE k=?",(k,)).fetchone()["v"]
def lang(uid):
    r=cur.execute("SELECT lang FROM users WHERE id=?",(uid,)).fetchone()
    return r["lang"] if r and r["lang"] else None
def text(row,l,field):
    return row[f"{field}_{l}"]
def label(row,l): return row[f"label_{l}"]
def main_kb(l):
    rows=cur.execute("SELECT * FROM menu WHERE active=1 ORDER BY sort").fetchall()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label(r,l),callback_data="m:"+r["action"])] for r in rows
    ])
def languages():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🇷🇺 Русский",callback_data="lang:ru")],
      [InlineKeyboardButton(text="🇱🇻 Latviešu",callback_data="lang:lv")],
      [InlineKeyboardButton(text="🇬🇧 English",callback_data="lang:en")]])
def back(l): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text={"ru":"⬅️ Назад","lv":"⬅️ Atpakaļ","en":"⬅️ Back"}[l],callback_data="home")]])

class Contact(StatesGroup): message=State()
class Order(StatesGroup): service=State(); text=State(); budget=State(); contact=State()
class AdminEdit(StatesGroup): value=State()
class ServiceAdd(StatesGroup): name=State(); desc=State(); price=State()

async def show_home(message_or_call,l):
    uid=message_or_call.from_user.id
    if isinstance(message_or_call,Message):
        if Path(LOGO_PATH).exists():
            await message_or_call.answer_photo(__import__('aiogram').types.FSInputFile(LOGO_PATH),caption=setting("welcome_"+l),reply_markup=main_kb(l),parse_mode="HTML")
        else: await message_or_call.answer(setting("welcome_"+l),reply_markup=main_kb(l),parse_mode="HTML")
    else:
        await message_or_call.message.edit_text(setting("welcome_"+l),reply_markup=main_kb(l),parse_mode="HTML")
        await message_or_call.answer()

@dp.message(CommandStart())
async def start(m:Message):
    cur.execute("INSERT OR IGNORE INTO users(id,name,username) VALUES(?,?,?)",(m.from_user.id,m.from_user.full_name,m.from_user.username)); conn.commit()
    l=lang(m.from_user.id)
    if not l:
        if Path(LOGO_PATH).exists(): await m.answer_photo(__import__('aiogram').types.FSInputFile(LOGO_PATH),caption="🌐 <b>Choose language / Выберите язык / Izvēlieties valodu</b>",reply_markup=languages(),parse_mode="HTML")
        else: await m.answer("🌐 Choose language / Выберите язык / Izvēlieties valodu",reply_markup=languages())
    else: await show_home(m,l)

@dp.callback_query(F.data.startswith("lang:"))
async def choose_lang(c:CallbackQuery):
    l=c.data.split(":")[1]
    cur.execute("UPDATE users SET lang=?,name=?,username=? WHERE id=?",(l,c.from_user.full_name,c.from_user.username,c.from_user.id)); conn.commit()
    await show_home(c,l)

@dp.callback_query(F.data=="home")
async def home(c:CallbackQuery): await show_home(c,lang(c.from_user.id) or "ru")

@dp.callback_query(F.data=="m:language")
async def change_lang(c:CallbackQuery):
    await c.message.edit_text("🌐 Выберите язык / Izvēlieties valodu / Choose language",reply_markup=languages()); await c.answer()

@dp.callback_query(F.data=="m:services")
async def services(c:CallbackQuery):
    l=lang(c.from_user.id) or "ru"; rows=cur.execute("SELECT * FROM services WHERE active=1 ORDER BY sort").fetchall()
    if not rows: await c.message.edit_text({"ru":"🛠 Услуги пока не добавлены.","lv":"🛠 Pakalpojumi vēl nav pievienoti.","en":"🛠 No services yet."}[l],reply_markup=back(l))
    else:
        buttons=[[InlineKeyboardButton(text=f"{r['name_'+l]} — {r['price_'+l]}",callback_data=f"svc:{r['id']}")] for r in rows]
        buttons.append([InlineKeyboardButton(text={"ru":"⬅️ Назад","lv":"⬅️ Atpakaļ","en":"⬅️ Back"}[l],callback_data="home")])
        await c.message.edit_text({"ru":"🛠 <b>Услуги</b>\n\nВыберите услугу:","lv":"🛠 <b>Pakalpojumi</b>\n\nIzvēlieties pakalpojumu:","en":"🛠 <b>Services</b>\n\nChoose a service:"}[l],reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data.startswith("svc:"))
async def service_detail(c:CallbackQuery):
    l=lang(c.from_user.id) or "ru"; r=cur.execute("SELECT * FROM services WHERE id=?",(int(c.data.split(":")[1]),)).fetchone()
    await c.message.edit_text(f"<b>{r['name_'+l]}</b>\n\n{r['desc_'+l]}\n\n💰 {r['price_'+l]}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text={"ru":"📝 Заказать","lv":"📝 Pasūtīt","en":"📝 Order"}[l],callback_data=f"order:{r['id']}")],[InlineKeyboardButton(text={"ru":"⬅️ Назад","lv":"⬅️ Atpakaļ","en":"⬅️ Back"}[l],callback_data="m:services")]]),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="m:prices")
async def prices(c:CallbackQuery):
    l=lang(c.from_user.id) or "ru"; rows=cur.execute("SELECT * FROM services WHERE active=1 ORDER BY sort").fetchall()
    body={"ru":"💰 <b>Цены</b>\n\n","lv":"💰 <b>Cenas</b>\n\n","en":"💰 <b>Prices</b>\n\n"}[l]+ "\n".join(f"• {r['name_'+l]} — {r['price_'+l]}" for r in rows)
    await c.message.edit_text(body,reply_markup=back(l),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="m:portfolio")
async def portfolio(c:CallbackQuery):
    l=lang(c.from_user.id) or "ru"; rows=cur.execute("SELECT * FROM portfolio WHERE active=1 ORDER BY sort").fetchall()
    if not rows: await c.message.edit_text({"ru":"🖼 Портфолио пока пусто.","lv":"🖼 Portfolio vēl ir tukšs.","en":"🖼 Portfolio is empty."}[l],reply_markup=back(l))
    else:
        for r in rows:
            await c.message.answer_photo(r["file_id"],caption=f"<b>{r['title_'+l]}</b>\n{r['desc_'+l]}",parse_mode="HTML")
        await c.message.answer({"ru":"🖼 Портфолио","lv":"🖼 Portfolio","en":"🖼 Portfolio"}[l],reply_markup=back(l))
        await c.message.delete()
    await c.answer()

@dp.callback_query(F.data=="m:contact")
async def contact(c:CallbackQuery,state:FSMContext):
    l=lang(c.from_user.id) or "ru"; await state.set_state(Contact.message)
    await c.message.edit_text(setting("contact_"+l),reply_markup=back(l),parse_mode="HTML"); await c.answer()

@dp.message(Contact.message)
async def contact_receive(m:Message,state:FSMContext):
    l=lang(m.from_user.id) or "ru"
    cur.execute("INSERT INTO requests(user_id,kind,text,contact) VALUES(?,?,?,?)",(m.from_user.id,"contact",m.text or "",f"@{m.from_user.username}" if m.from_user.username else str(m.from_user.id))); conn.commit()
    if ADMIN_ID: await bot.send_message(ADMIN_ID,f"📩 <b>Новое сообщение</b>\n👤 {m.from_user.full_name}\n🆔 <code>{m.from_user.id}</code>\n💬 @{m.from_user.username or 'нет'}\n\n{m.text or ''}",parse_mode="HTML")
    await state.clear(); await m.answer(setting("ack_"+l),reply_markup=main_kb(l),parse_mode="HTML")

@dp.callback_query(F.data.startswith("order:"))
async def order_start(c:CallbackQuery,state:FSMContext):
    l=lang(c.from_user.id) or "ru"; sid=int(c.data.split(":")[1]); r=cur.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone()
    await state.update_data(service=r["name_"+l]); await state.set_state(Order.text)
    await c.message.edit_text({"ru":"📝 Опишите задачу:","lv":"📝 Aprakstiet uzdevumu:","en":"📝 Describe your task:"}[l],reply_markup=back(l)); await c.answer()

@dp.callback_query(F.data=="m:order")
async def generic_order(c:CallbackQuery,state:FSMContext):
    l=lang(c.from_user.id) or "ru"; await state.update_data(service="Не указана"); await state.set_state(Order.text)
    await c.message.edit_text({"ru":"📝 Опишите, что вам нужно:","lv":"📝 Aprakstiet, kas jums nepieciešams:","en":"📝 Describe what you need:"}[l],reply_markup=back(l)); await c.answer()

@dp.message(Order.text)
async def order_text(m:Message,state:FSMContext):
    l=lang(m.from_user.id) or "ru"; await state.update_data(text=m.text or ""); await state.set_state(Order.budget)
    await m.answer({"ru":"💰 Укажите бюджет или напишите «не знаю»:","lv":"💰 Norādiet budžetu vai rakstiet «nezinu»:","en":"💰 Enter your budget or type “I don't know”:"}[l])

@dp.message(Order.budget)
async def order_budget(m:Message,state:FSMContext):
    await state.update_data(budget=m.text or ""); await state.set_state(Order.contact)
    l=lang(m.from_user.id) or "ru"; await m.answer({"ru":"📞 Оставьте контакт для связи:","lv":"📞 Norādiet kontaktinformāciju:","en":"📞 Leave a contact:"}[l])

@dp.message(Order.contact)
async def order_contact(m:Message,state:FSMContext):
    l=lang(m.from_user.id) or "ru"; d=await state.get_data()
    cur.execute("INSERT INTO requests(user_id,kind,service,budget,contact,text) VALUES(?,?,?,?,?,?)",(m.from_user.id,"order",d.get("service",""),d.get("budget",""),m.text or "",d.get("text",""))); conn.commit()
    if ADMIN_ID: await bot.send_message(ADMIN_ID,f"🆕 <b>Новая заявка</b>\n👤 {m.from_user.full_name}\n🆔 <code>{m.from_user.id}</code>\n🛠 {d.get('service','')}\n💰 {d.get('budget','')}\n📞 {m.text or ''}\n📝 {d.get('text','')}",parse_mode="HTML")
    await state.clear(); await m.answer(setting("ack_"+l),reply_markup=main_kb(l),parse_mode="HTML")

# ADMIN
def is_admin(uid): return ADMIN_ID and uid==ADMIN_ID
def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text="🛠 Услуги",callback_data="a:services"),InlineKeyboardButton(text="💰 Цены",callback_data="a:prices")],
      [InlineKeyboardButton(text="✏️ Тексты",callback_data="a:texts"),InlineKeyboardButton(text="🔘 Меню",callback_data="a:menu")],
      [InlineKeyboardButton(text="🖼 Портфолио",callback_data="a:portfolio"),InlineKeyboardButton(text="📥 Заявки",callback_data="a:requests")],
    ])
@dp.message(Command("admin"))
async def admin(m:Message):
    if not is_admin(m.from_user.id): return
    await m.answer("🔐 <b>ZYVERON Admin</b>\n\nВыберите раздел:",reply_markup=admin_kb(),parse_mode="HTML")

@dp.callback_query(F.data=="a:prices")
async def a_prices(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows=cur.execute("SELECT * FROM services ORDER BY sort").fetchall()
    kb=[[InlineKeyboardButton(text=f"💰 {r['name_ru']}",callback_data=f"a:price:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Админ-панель",callback_data="a:home")])
    await c.message.edit_text("💰 <b>Изменение цен</b>\n\nВыберите услугу:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("a:price:"))
async def a_price(c:CallbackQuery,state:FSMContext):
    if not is_admin(c.from_user.id): return
    sid=int(c.data.split(":")[2]); await state.update_data(mode="price",sid=sid); await state.set_state(AdminEdit.value)
    await c.message.edit_text("Введите новое значение цены. Можно написать число или любой текст:\n\nПримеры: <code>50 €</code>, <code>от €50</code>, <code>по запросу</code>, <code>недоступно</code>",parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="a:texts")
async def a_texts(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    kb=[]
    for k in ["welcome","ack","contact"]:
        for l,n in [("ru","🇷🇺"),("lv","🇱🇻"),("en","🇬🇧")]:
            kb.append([InlineKeyboardButton(text=f"{n} {k}",callback_data=f"a:text:{k}:{l}")])
    kb.append([InlineKeyboardButton(text="⬅️ Админ-панель",callback_data="a:home")])
    await c.message.edit_text("✏️ Выберите текст:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()
@dp.callback_query(F.data.startswith("a:text:"))
async def a_text(c:CallbackQuery,state:FSMContext):
    if not is_admin(c.from_user.id): return
    _,_,k,l=c.data.split(":"); await state.update_data(mode="text",key=f"{k}_{l}"); await state.set_state(AdminEdit.value)
    await c.message.edit_text(f"Отправьте новый текст для <b>{k} / {l}</b>.",parse_mode="HTML"); await c.answer()

@dp.message(AdminEdit.value)
async def admin_value(m:Message,state:FSMContext):
    if not is_admin(m.from_user.id): return
    d=await state.get_data()
    if d.get("mode")=="price":
        cur.execute(f"UPDATE services SET price_ru=price_ru, price_lv=price_lv, price_en=price_en WHERE id=?",(d["sid"],))
        # Set all language prices to supplied value; admin can use text in all languages.
        cur.execute("UPDATE services SET price_ru=?,price_lv=?,price_en=? WHERE id=?",(m.text,m.text,m.text,d["sid"]))
    elif d.get("mode")=="text":
        cur.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(d["key"],m.text))
    conn.commit(); await state.clear(); await m.answer("✅ Сохранено.\n\nОткройте /admin для продолжения.",reply_markup=admin_kb())

@dp.callback_query(F.data=="a:home")
async def a_home(c:CallbackQuery):
    if is_admin(c.from_user.id): await c.message.edit_text("🔐 <b>ZYVERON Admin</b>",reply_markup=admin_kb(),parse_mode="HTML")
    await c.answer()

@dp.callback_query(F.data=="a:services")
async def a_services(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows=cur.execute("SELECT * FROM services ORDER BY sort").fetchall()
    kb=[[InlineKeyboardButton(text=("🟢 " if r["active"] else "🔴 ")+r["name_ru"],callback_data=f"a:svc:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="➕ Добавить услугу",callback_data="a:addsvc")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")])
    await c.message.edit_text("🛠 Управление услугами:",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)); await c.answer()
@dp.callback_query(F.data.startswith("a:svc:"))
async def a_svc(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    sid=int(c.data.split(":")[2]); r=cur.execute("SELECT * FROM services WHERE id=?",(sid,)).fetchone()
    kb=[[InlineKeyboardButton(text="💰 Цена",callback_data=f"a:price:{sid}")],
        [InlineKeyboardButton(text="🗑 Удалить",callback_data=f"a:del:{sid}"),
         InlineKeyboardButton(text="🔄 Вкл/выкл",callback_data=f"a:toggle:{sid}")],
        [InlineKeyboardButton(text="⬅️ Назад",callback_data="a:services")]]
    await c.message.edit_text(f"<b>{r['name_ru']}</b>\n\n{r['desc_ru']}\n\n💰 {r['price_ru']}",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data.startswith("a:del:"))
async def a_del(c:CallbackQuery):
    if is_admin(c.from_user.id): cur.execute("DELETE FROM services WHERE id=?",(int(c.data.split(":")[2]),)); conn.commit(); await a_services(c)
@dp.callback_query(F.data.startswith("a:toggle:"))
async def a_toggle(c:CallbackQuery):
    if is_admin(c.from_user.id):
        sid=int(c.data.split(":")[2]); cur.execute("UPDATE services SET active=1-active WHERE id=?",(sid,)); conn.commit(); await a_services(c)

@dp.callback_query(F.data=="a:requests")
async def a_requests(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows=cur.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 20").fetchall()
    if not rows: body="📥 Заявок пока нет."
    else: body="\n\n".join(f"#{r['id']} • {r['kind']} • {r['status']}\n👤 <code>{r['user_id']}</code>\n🛠 {r['service'] or '-'}\n💰 {r['budget'] or '-'}\n📝 {r['text'] or '-'}\n📞 {r['contact'] or '-'}" for r in rows)
    await c.message.edit_text("📥 <b>Последние заявки</b>\n\n"+body,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]),parse_mode="HTML"); await c.answer()

@dp.callback_query(F.data=="a:portfolio")
async def a_portfolio(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows=cur.execute("SELECT * FROM portfolio ORDER BY sort").fetchall()
    kb=[[InlineKeyboardButton(text=f"🗑 {r['title_ru']}",callback_data=f"a:pdel:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="📸 Чтобы добавить работу: отправьте фото боту",callback_data="a:home")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")])
    await c.message.edit_text("🖼 <b>Портфолио</b>\n\n"+("\n".join(f"• {r['title_ru']}" for r in rows) if rows else "Пока пусто."),reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await c.answer()

@dp.message(F.photo)
async def photo_admin(m:Message):
    if not is_admin(m.from_user.id): return
    fid=m.photo[-1].file_id
    cur.execute("INSERT INTO portfolio(file_id,title_ru,title_lv,title_en,desc_ru,desc_lv,desc_en) VALUES(?,?,?,?,?,?,?)",(fid,"Новая работа","Jauns darbs","New work","","","")); conn.commit()
    await m.answer("📸 Фото добавлено в портфолио. Название/описание можно доработать в админ-панели.")

@dp.callback_query(F.data.startswith("a:pdel:"))
async def pdel(c:CallbackQuery):
    if is_admin(c.from_user.id): cur.execute("DELETE FROM portfolio WHERE id=?",(int(c.data.split(":")[2]),)); conn.commit(); await a_portfolio(c)

@dp.callback_query(F.data=="a:menu")
async def a_menu(c:CallbackQuery):
    if not is_admin(c.from_user.id): return
    rows=cur.execute("SELECT * FROM menu ORDER BY sort").fetchall()
    kb=[[InlineKeyboardButton(text=("🟢 " if r["active"] else "🔴 ")+r["label_ru"],callback_data=f"a:m:{r['id']}")] for r in rows]
    kb.append([InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")])
    await c.message.edit_text("🔘 <b>Структура главного меню</b>\n\nВыберите кнопку для включения/выключения.",reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),parse_mode="HTML"); await c.answer()
@dp.callback_query(F.data.startswith("a:m:"))
async def a_menu_toggle(c:CallbackQuery):
    if is_admin(c.from_user.id):
        mid=int(c.data.split(":")[2]); cur.execute("UPDATE menu SET active=1-active WHERE id=?",(mid,)); conn.commit(); await a_menu(c)

async def main(): await dp.start_polling(bot)
if __name__=="__main__": asyncio.run(main())
