import os
import asyncio
import logging
import sqlite3
import html
from pathlib import Path
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or 0)
DB_PATH = os.getenv("DB_PATH", "/opt/render/project/src/data/zyveron.db")
LOGO_PATH = os.getenv("LOGO_PATH", "media/logo.jpg")
LANGS = {"ru", "lv", "en"}
ROLES = ("owner", "senior_admin", "admin")
ROLE_NAME = {"owner": "Owner", "senior_admin": "Senior Admin", "admin": "Admin"}
if not TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

bot = Bot(TOKEN)
dp = Dispatcher(storage=MemoryStorage())
conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
conn.row_factory = sqlite3.Row
db_lock = asyncio.Lock()

TRANSLATIONS = {
 "ru": {"choose_language":"🌐 <b>Выберите язык</b>","back":"⬅️ Назад","services":"🛠 <b>Услуги</b>\n\nВыберите услугу:","no_services":"🛠 Услуги пока не добавлены.","prices":"💰 <b>Цены</b>","portfolio":"🖼 Портфолио","empty_portfolio":"🖼 Портфолио пока пусто.","describe":"📝 Опишите задачу:","describe_generic":"📝 Опишите, что вам нужно:","budget":"💰 Укажите бюджет или напишите «не знаю»:","contact_prompt":"📞 Оставьте контакт для связи:","order":"📝 Заказать"},
 "lv": {"choose_language":"🌐 <b>Izvēlieties valodu</b>","back":"⬅️ Atpakaļ","services":"🛠 <b>Pakalpojumi</b>\n\nIzvēlieties pakalpojumu:","no_services":"🛠 Pakalpojumi vēl nav pievienoti.","prices":"💰 <b>Cenas</b>","portfolio":"🖼 Portfolio","empty_portfolio":"🖼 Portfolio vēl ir tukšs.","describe":"📝 Aprakstiet uzdevumu:","describe_generic":"📝 Aprakstiet, kas jums nepieciešams:","budget":"💰 Norādiet budžetu vai rakstiet «nezinu»:","contact_prompt":"📞 Norādiet kontaktinformāciju:","order":"📝 Pasūtīt"},
 "en": {"choose_language":"🌐 <b>Choose language</b>","back":"⬅️ Back","services":"🛠 <b>Services</b>\n\nChoose a service:","no_services":"🛠 No services yet.","prices":"💰 <b>Prices</b>","portfolio":"🖼 Portfolio","empty_portfolio":"🖼 Portfolio is empty.","describe":"📝 Describe your task:","describe_generic":"📝 Describe what you need:","budget":"💰 Enter your budget or type “I don't know”:","contact_prompt":"📞 Leave a contact:","order":"📝 Order"}
}
DEFAULTS = {
"welcome_ru":"👋 Добро пожаловать в <b>ZYVERON</b>!\n\nЦифровые решения для бизнеса: Telegram-боты, автоматизация, сайты и разработка.",
"welcome_lv":"👋 Laipni lūdzam <b>ZYVERON</b>!\n\nDigitālie risinājumi uzņēmumiem: Telegram roboti, automatizācija, mājaslapas un izstrāde.",
"welcome_en":"👋 Welcome to <b>ZYVERON</b>!\n\nDigital solutions for businesses: Telegram bots, automation, websites and development.",
"ack_ru":"✅ <b>Спасибо! Ваша заявка принята.</b>\nМы получили ваше сообщение и ответим на него как можно скорее.",
"ack_lv":"✅ <b>Paldies! Jūsu pieteikums ir saņemts.</b>\nMēs to izskatīsim un atbildēsim pēc iespējas ātrāk.",
"ack_en":"✅ <b>Thank you! Your request has been received.</b>\nWe will review it and get back to you as soon as possible.",
"contact_ru":"💬 <b>Связаться с ZYVERON</b>\n\nНапишите ваше сообщение одним сообщением.",
"contact_lv":"💬 <b>Sazināties ar ZYVERON</b>\n\nNosūtiet savu ziņu vienā ziņā.",
"contact_en":"💬 <b>Contact ZYVERON</b>\n\nSend your message in one message."
}
MENU_DEFAULTS=[("services","🛠 Услуги","🛠 Pakalpojumi","🛠 Services","services",1,1),("prices","💰 Цены","💰 Cenas","💰 Prices","prices",1,2),("portfolio","🖼 Портфолио","🖼 Portfolio","🖼 Portfolio","portfolio",1,3),("order","📝 Заказать","📝 Pasūtīt","📝 Order","order",1,4),("contact","📞 Связаться","📞 Sazināties","📞 Contact","contact",1,5),("language","🌐 Язык","🌐 Valoda","🌐 Language","language",1,6)]
settings_cache: dict[str,str] = {}
lang_cache: dict[int,str] = {}
menu_cache: list[dict] = []
admins_cache: dict[int,str] = {}

class Contact(StatesGroup): message = State()
class Order(StatesGroup): text=State(); budget=State(); contact=State()
class AdminEdit(StatesGroup): value=State()
class ServiceAdd(StatesGroup): name=State(); desc=State(); price=State()
class AdminAdd(StatesGroup): user_id=State(); role=State()

async def db_execute(sql, params=()):
    async with db_lock:
        return conn.execute(sql, params)
async def db_fetchone(sql, params=()):
    async with db_lock:
        return conn.execute(sql, params).fetchone()
async def db_fetchall(sql, params=()):
    async with db_lock:
        return conn.execute(sql, params).fetchall()

async def initialise():
    async with db_lock:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,lang TEXT,name TEXT,username TEXT);
        CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT,name_ru TEXT,name_lv TEXT,name_en TEXT,desc_ru TEXT,desc_lv TEXT,desc_en TEXT,price_ru TEXT,price_lv TEXT,price_en TEXT,active INTEGER DEFAULT 1,sort INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS menu(id INTEGER PRIMARY KEY AUTOINCREMENT,key TEXT UNIQUE,label_ru TEXT,label_lv TEXT,label_en TEXT,action TEXT,active INTEGER DEFAULT 1,sort INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS portfolio(id INTEGER PRIMARY KEY AUTOINCREMENT,file_id TEXT,title_ru TEXT,title_lv TEXT,title_en TEXT,desc_ru TEXT,desc_lv TEXT,desc_en TEXT,active INTEGER DEFAULT 1,sort INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,service TEXT,budget TEXT,contact TEXT,text TEXT,status TEXT DEFAULT 'new',created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS administrators(user_id INTEGER PRIMARY KEY,role TEXT NOT NULL CHECK(role IN ('owner','senior_admin','admin')),added_by INTEGER,created TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS idx_services_active_sort ON services(active,sort);
        CREATE INDEX IF NOT EXISTS idx_portfolio_active_sort ON portfolio(active,sort);
        CREATE INDEX IF NOT EXISTS idx_requests_id ON requests(id DESC);
        CREATE INDEX IF NOT EXISTS idx_admin_role ON administrators(role);
        """)
        for k,v in DEFAULTS.items(): conn.execute("INSERT OR IGNORE INTO settings(k,v) VALUES(?,?)",(k,v))
        for x in MENU_DEFAULTS: conn.execute("INSERT OR IGNORE INTO menu(key,label_ru,label_lv,label_en,action,active,sort) VALUES(?,?,?,?,?,?,?)",x)
        count=conn.execute("SELECT COUNT(*) FROM administrators").fetchone()[0]
        if count == 0 and ADMIN_ID:
            conn.execute("INSERT OR IGNORE INTO administrators(user_id,role,added_by) VALUES(?,?,?)",(ADMIN_ID,"owner",ADMIN_ID))
    await refresh_caches()

async def refresh_caches():
    global settings_cache, menu_cache, admins_cache
    async with db_lock:
        settings_cache={r["k"]:r["v"] for r in conn.execute("SELECT k,v FROM settings")}
        menu_cache=[dict(r) for r in conn.execute("SELECT * FROM menu WHERE active=1 ORDER BY sort")]
        admins_cache={r["user_id"]:r["role"] for r in conn.execute("SELECT user_id,role FROM administrators")}

def lang_of(uid): return lang_cache.get(uid,"ru")
def tr(lang,key): return TRANSLATIONS.get(lang,TRANSLATIONS["ru"]).get(key,key)
def setting(key): return settings_cache.get(key, DEFAULTS.get(key,""))
def role_of(uid): return admins_cache.get(uid)
def allowed(uid, *roles): return role_of(uid) in roles
def can_manage_admin(actor, target_role):
    ar=role_of(actor)
    return ar=="owner" or (ar=="senior_admin" and target_role=="admin")
def esc(v): return html.escape(str(v or ""))

def languages(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇷🇺 Русский",callback_data="lang:ru")],[InlineKeyboardButton(text="🇱🇻 Latviešu",callback_data="lang:lv")],[InlineKeyboardButton(text="🇬🇧 English",callback_data="lang:en")]])
def back(l): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr(l,"back"),callback_data="home")]])
def main_kb(l): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=r.get("label_"+l) or r["label_ru"],callback_data="m:"+r["action"])] for r in menu_cache])
def admin_kb(uid):
    role=role_of(uid); rows=[]
    if role in ("owner","senior_admin"): rows += [[InlineKeyboardButton(text="🛠 Услуги",callback_data="a:services"),InlineKeyboardButton(text="💰 Цены",callback_data="a:prices")],[InlineKeyboardButton(text="🖼 Портфолио",callback_data="a:portfolio"),InlineKeyboardButton(text="📥 Заявки",callback_data="a:requests")]]
    else: rows += [[InlineKeyboardButton(text="📥 Заявки",callback_data="a:requests")]]
    if role=="owner": rows += [[InlineKeyboardButton(text="✏️ Тексты",callback_data="a:texts"),InlineKeyboardButton(text="🔘 Меню",callback_data="a:menu")]]
    if role in ("owner","senior_admin"): rows += [[InlineKeyboardButton(text="👥 Администраторы",callback_data="a:admins")]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def answer_callback(c, text=None, alert=False):
    try: await c.answer(text,show_alert=alert)
    except TelegramAPIError: pass
async def edit(c,text,markup=None,parse_mode="HTML"):
    try: await c.message.edit_text(text,reply_markup=markup,parse_mode=parse_mode)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e).lower(): raise

async def show_home(obj,l):
    l=l if l in LANGS else "ru"
    caption=setting("welcome_"+l)
    if isinstance(obj,Message):
        if Path(LOGO_PATH).is_file(): await obj.answer_photo(FSInputFile(LOGO_PATH),caption=caption,reply_markup=main_kb(l),parse_mode="HTML")
        else: await obj.answer(caption,reply_markup=main_kb(l),parse_mode="HTML")
    else: await edit(obj,caption,main_kb(l))

async def require(c, *roles):
    if allowed(c.from_user.id,*roles): return True
    await answer_callback(c,"Недостаточно прав",True); return False

@dp.message(CommandStart())
async def start(m:Message):
    async with db_lock:
        conn.execute("INSERT INTO users(id,name,username) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,username=excluded.username",(m.from_user.id,m.from_user.full_name,m.from_user.username))
        row=conn.execute("SELECT lang FROM users WHERE id=?",(m.from_user.id,)).fetchone()
    if row and row["lang"] in LANGS: lang_cache[m.from_user.id]=row["lang"]
    l=lang_cache.get(m.from_user.id)
    if l: await show_home(m,l)
    else: await m.answer(tr("ru","choose_language"),reply_markup=languages(),parse_mode="HTML")

@dp.callback_query(F.data=="m:language")
async def change_language(c):
    await answer_callback(c)
    await edit(c,tr(lang_of(c.from_user.id),"choose_language"),languages())
@dp.callback_query(F.data.startswith("lang:"))
async def choose_language(c):
    data=c.data.split(":",1)
    l=data[1] if len(data)==2 else ""
    await answer_callback(c)
    if l not in LANGS: return
    lang_cache[c.from_user.id]=l
    async with db_lock:
        conn.execute("INSERT INTO users(id,lang,name,username) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET lang=excluded.lang,name=excluded.name,username=excluded.username",(c.from_user.id,l,c.from_user.full_name,c.from_user.username))
    await show_home(c,l)
@dp.callback_query(F.data=="home")
async def home(c):
    await answer_callback(c); await show_home(c,lang_of(c.from_user.id))

@dp.callback_query(F.data=="m:services")
async def services(c):
    await answer_callback(c); l=lang_of(c.from_user.id); rows=await db_fetchall("SELECT * FROM services WHERE active=1 ORDER BY sort,id")
    if not rows: return await edit(c,tr(l,"no_services"),back(l))
    buttons=[[InlineKeyboardButton(text=f"{esc(r['name_'+l])} — {esc(r['price_'+l])}",callback_data=f"svc:{r['id']}")] for r in rows]+[[InlineKeyboardButton(text=tr(l,"back"),callback_data="home")]]
    await edit(c,tr(l,"services"),InlineKeyboardMarkup(inline_keyboard=buttons))
@dp.callback_query(F.data.startswith("svc:"))
async def service_detail(c):
    await answer_callback(c); l=lang_of(c.from_user.id)
    try: sid=int(c.data.split(":",1)[1])
    except (ValueError,IndexError): return
    r=await db_fetchone("SELECT * FROM services WHERE id=? AND active=1",(sid,))
    if not r: return await answer_callback(c,"Услуга недоступна",True)
    body=f"<b>{esc(r['name_'+l])}</b>\n\n{esc(r['desc_'+l])}\n\n💰 {esc(r['price_'+l])}"
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=tr(l,"order"),callback_data=f"order:{sid}")],[InlineKeyboardButton(text=tr(l,"back"),callback_data="m:services")]])
    await edit(c,body,kb)
@dp.callback_query(F.data=="m:prices")
async def prices(c):
    await answer_callback(c); l=lang_of(c.from_user.id); rows=await db_fetchall("SELECT * FROM services WHERE active=1 ORDER BY sort,id")
    body=tr(l,"prices")+"\n\n"+"\n".join(f"• {esc(r['name_'+l])} — {esc(r['price_'+l])}" for r in rows)
    await edit(c,body,back(l))
@dp.callback_query(F.data=="m:portfolio")
async def portfolio(c):
    await answer_callback(c); l=lang_of(c.from_user.id); rows=await db_fetchall("SELECT * FROM portfolio WHERE active=1 ORDER BY sort,id")
    if not rows: return await edit(c,tr(l,"empty_portfolio"),back(l))
    for r in rows:
        try: await c.message.answer_photo(r["file_id"],caption=f"<b>{esc(r['title_'+l])}</b>\n{esc(r['desc_'+l])}",parse_mode="HTML")
        except TelegramAPIError: log.exception("Portfolio photo failed")
    await c.message.answer(tr(l,"portfolio"),reply_markup=back(l)); await c.message.delete()
@dp.callback_query(F.data=="m:contact")
async def contact(c,state):
    await answer_callback(c); l=lang_of(c.from_user.id); await state.set_state(Contact.message); await edit(c,setting("contact_"+l),back(l))
@dp.message(Contact.message)
async def contact_receive(m,state):
    l=lang_of(m.from_user.id); value=m.text or m.caption or ""
    await db_execute("INSERT INTO requests(user_id,kind,text,contact) VALUES(?,?,?,?)",(m.from_user.id,"contact",value,"@"+m.from_user.username if m.from_user.username else str(m.from_user.id)))
    for uid in [u for u,r in admins_cache.items() if r in ROLES]:
        try: await bot.send_message(uid,f"📩 <b>Новое сообщение</b>\n👤 {esc(m.from_user.full_name)}\n🆔 <code>{m.from_user.id}</code>\n\n{esc(value)}",parse_mode="HTML")
        except TelegramAPIError: log.warning("Cannot notify admin %s",uid)
    await state.clear(); await m.answer(setting("ack_"+l),reply_markup=main_kb(l),parse_mode="HTML")
@dp.callback_query(F.data.startswith("order:"))
async def order_start(c,state):
    await answer_callback(c); l=lang_of(c.from_user.id)
    try: sid=int(c.data.split(":",1)[1])
    except (ValueError,IndexError): return
    r=await db_fetchone("SELECT * FROM services WHERE id=? AND active=1",(sid,))
    if not r: return await answer_callback(c,"Услуга недоступна",True)
    await state.update_data(service=r["name_"+l]); await state.set_state(Order.text); await edit(c,tr(l,"describe"),back(l))
@dp.callback_query(F.data=="m:order")
async def generic_order(c,state):
    await answer_callback(c); l=lang_of(c.from_user.id); await state.update_data(service="Не указана"); await state.set_state(Order.text); await edit(c,tr(l,"describe_generic"),back(l))
@dp.message(Order.text)
async def order_text(m,state):
    await state.update_data(text=m.text or ""); await state.set_state(Order.budget); await m.answer(tr(lang_of(m.from_user.id),"budget"))
@dp.message(Order.budget)
async def order_budget(m,state):
    await state.update_data(budget=m.text or ""); await state.set_state(Order.contact); await m.answer(tr(lang_of(m.from_user.id),"contact_prompt"))
@dp.message(Order.contact)
async def order_contact(m,state):
    l=lang_of(m.from_user.id); d=await state.get_data(); contact=m.text or ""
    await db_execute("INSERT INTO requests(user_id,kind,service,budget,contact,text) VALUES(?,?,?,?,?,?)",(m.from_user.id,"order",d.get("service",""),d.get("budget",""),contact,d.get("text","")))
    for uid in admins_cache:
        try: await bot.send_message(uid,f"🆕 <b>Новая заявка</b>\n👤 {esc(m.from_user.full_name)}\n🆔 <code>{m.from_user.id}</code>\n🛠 {esc(d.get('service'))}\n💰 {esc(d.get('budget'))}\n📞 {esc(contact)}\n📝 {esc(d.get('text'))}",parse_mode="HTML")
        except TelegramAPIError: pass
    await state.clear(); await m.answer(setting("ack_"+l),reply_markup=main_kb(l),parse_mode="HTML")

@dp.message(Command("admin"))
async def admin(m):
    if not role_of(m.from_user.id): return
    await m.answer("🔐 <b>ZYVERON Admin</b>\n\nВыберите раздел:",reply_markup=admin_kb(m.from_user.id),parse_mode="HTML")
@dp.callback_query(F.data=="a:home")
async def a_home(c):
    if not await require(c,*ROLES): return
    await answer_callback(c); await edit(c,"🔐 <b>ZYVERON Admin</b>",admin_kb(c.from_user.id))
@dp.callback_query(F.data=="a:requests")
async def a_requests(c):
    if not await require(c,*ROLES): return
    await answer_callback(c); rows=await db_fetchall("SELECT * FROM requests ORDER BY id DESC LIMIT 20")
    body="📥 Заявок пока нет." if not rows else "\n\n".join(f"#{r['id']} • {esc(r['kind'])} • {esc(r['status'])}\n👤 <code>{r['user_id']}</code>\n🛠 {esc(r['service'] or '-')}\n💰 {esc(r['budget'] or '-')}\n📝 {esc(r['text'] or '-')}\n📞 {esc(r['contact'] or '-')}" for r in rows)
    await edit(c,"📥 <b>Последние заявки</b>\n\n"+body,InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]))
@dp.callback_query(F.data.in_({"a:services","a:prices","a:portfolio"}))
async def admin_sections(c):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c)
    if c.data=="a:services":
        rows=await db_fetchall("SELECT * FROM services ORDER BY sort,id"); kb=[[InlineKeyboardButton(text=("🟢 " if r['active'] else "🔴 ")+esc(r['name_ru']),callback_data=f"a:svc:{r['id']}")] for r in rows]+[[InlineKeyboardButton(text="➕ Добавить услугу",callback_data="a:addsvc")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]; await edit(c,"🛠 Управление услугами:",InlineKeyboardMarkup(inline_keyboard=kb)); return
    if c.data=="a:prices":
        rows=await db_fetchall("SELECT * FROM services ORDER BY sort,id"); kb=[[InlineKeyboardButton(text="💰 "+esc(r['name_ru']),callback_data=f"a:price:{r['id']}")] for r in rows]+[[InlineKeyboardButton(text="⬅️ Админ-панель",callback_data="a:home")]]; await edit(c,"💰 <b>Изменение цен</b>",InlineKeyboardMarkup(inline_keyboard=kb)); return
    rows=await db_fetchall("SELECT * FROM portfolio ORDER BY sort,id"); kb=[[InlineKeyboardButton(text="🗑 "+esc(r['title_ru']),callback_data=f"a:pdel:{r['id']}")] for r in rows]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]; await edit(c,"🖼 <b>Портфолио</b>\n\n"+("\n".join("• "+esc(r['title_ru']) for r in rows) if rows else "Пока пусто."),InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data.startswith("a:price:"))
async def a_price(c,state):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c)
    try: sid=int(c.data.rsplit(":",1)[1])
    except ValueError: return
    if not await db_fetchone("SELECT id FROM services WHERE id=?",(sid,)): return
    await state.update_data(mode="price",sid=sid); await state.set_state(AdminEdit.value); await edit(c,"Введите новую цену для всех языков:")
@dp.callback_query(F.data.startswith("a:svc:"))
async def a_service(c):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c)
    try: sid=int(c.data.rsplit(":",1)[1])
    except ValueError:return
    r=await db_fetchone("SELECT * FROM services WHERE id=?",(sid,))
    if not r:return
    kb=[[InlineKeyboardButton(text="💰 Цена",callback_data=f"a:price:{sid}")],[InlineKeyboardButton(text="🗑 Удалить",callback_data=f"a:del:{sid}"),InlineKeyboardButton(text="🔄 Вкл/выкл",callback_data=f"a:toggle:{sid}")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:services")]]
    await edit(c,f"<b>{esc(r['name_ru'])}</b>\n\n{esc(r['desc_ru'])}\n\n💰 {esc(r['price_ru'])}",InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data.startswith("a:del:") | F.data.startswith("a:toggle:") | F.data.startswith("a:pdel:"))
async def admin_change_content(c):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c)
    try: kind,sid=c.data.rsplit(":",1); sid=int(sid)
    except ValueError:return
    if kind=="a:del": await db_execute("DELETE FROM services WHERE id=?",(sid,)); await admin_sections_proxy(c,"a:services")
    elif kind=="a:toggle": await db_execute("UPDATE services SET active=1-active WHERE id=?",(sid,)); await admin_sections_proxy(c,"a:services")
    else: await db_execute("DELETE FROM portfolio WHERE id=?",(sid,)); await admin_sections_proxy(c,"a:portfolio")
async def admin_sections_proxy(c,data):
    c.data=data; await admin_sections(c)
@dp.callback_query(F.data=="a:addsvc")
async def add_service(c,state):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c); await state.set_state(ServiceAdd.name); await edit(c,"Введите название услуги (будет использовано для всех языков):")
@dp.message(ServiceAdd.name)
async def add_service_name(m,state): await state.update_data(name=m.text or ""); await state.set_state(ServiceAdd.desc); await m.answer("Введите описание:")
@dp.message(ServiceAdd.desc)
async def add_service_desc(m,state): await state.update_data(desc=m.text or ""); await state.set_state(ServiceAdd.price); await m.answer("Введите цену:")
@dp.message(ServiceAdd.price)
async def add_service_price(m,state):
    if not allowed(m.from_user.id,"owner","senior_admin"): return
    d=await state.get_data(); await db_execute("INSERT INTO services(name_ru,name_lv,name_en,desc_ru,desc_lv,desc_en,price_ru,price_lv,price_en,sort) VALUES(?,?,?,?,?,?,?,?,?,COALESCE((SELECT MAX(sort)+1 FROM services),1))",(d['name'],d['name'],d['name'],d['desc'],d['desc'],d['desc'],m.text or '',m.text or '',m.text or '')); await state.clear(); await m.answer("✅ Услуга добавлена.",reply_markup=admin_kb(m.from_user.id))
@dp.message(F.photo)
async def photo_admin(m):
    if not allowed(m.from_user.id,"owner","senior_admin"): return
    await db_execute("INSERT INTO portfolio(file_id,title_ru,title_lv,title_en,desc_ru,desc_lv,desc_en) VALUES(?,?,?,?,?,?,?)",(m.photo[-1].file_id,"Новая работа","Jauns darbs","New work","","","")); await m.answer("📸 Фото добавлено в портфолио.")
@dp.callback_query(F.data=="a:texts")
async def a_texts(c):
    if not await require(c,"owner"): return
    await answer_callback(c); kb=[[InlineKeyboardButton(text=f"{flag} {key}",callback_data=f"a:text:{key}:{l}")] for key in ("welcome","ack","contact") for l,flag in (("ru","🇷🇺"),("lv","🇱🇻"),("en","🇬🇧"))]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]; await edit(c,"✏️ Выберите текст:",InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data.startswith("a:text:"))
async def a_text(c,state):
    if not await require(c,"owner"): return
    parts=c.data.split(":")
    if len(parts)!=4 or parts[2] not in {"welcome","ack","contact"} or parts[3] not in LANGS:return
    await answer_callback(c); await state.update_data(mode="text",key=f"{parts[2]}_{parts[3]}"); await state.set_state(AdminEdit.value); await edit(c,"Отправьте новый текст.")
@dp.message(AdminEdit.value)
async def admin_value(m,state):
    if not role_of(m.from_user.id): return
    d=await state.get_data(); value=m.text or ""
    if d.get("mode")=="price" and allowed(m.from_user.id,"owner","senior_admin"): await db_execute("UPDATE services SET price_ru=?,price_lv=?,price_en=? WHERE id=?",(value,value,value,d.get("sid")))
    elif d.get("mode")=="text" and allowed(m.from_user.id,"owner"):
        await db_execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(d.get("key"),value)); await refresh_caches()
    else:return
    await state.clear(); await m.answer("✅ Сохранено.",reply_markup=admin_kb(m.from_user.id))
@dp.callback_query(F.data=="a:menu")
async def a_menu(c):
    if not await require(c,"owner"): return
    await answer_callback(c); rows=await db_fetchall("SELECT * FROM menu ORDER BY sort,id"); kb=[[InlineKeyboardButton(text=("🟢 " if r['active'] else "🔴 ")+esc(r['label_ru']),callback_data=f"a:m:{r['id']}")] for r in rows]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]; await edit(c,"🔘 <b>Структура главного меню</b>",InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data.startswith("a:m:"))
async def a_menu_toggle(c):
    if not await require(c,"owner"): return
    await answer_callback(c)
    try: mid=int(c.data.rsplit(":",1)[1])
    except ValueError:return
    await db_execute("UPDATE menu SET active=1-active WHERE id=?",(mid,)); await refresh_caches(); await a_menu(c)

@dp.callback_query(F.data=="a:admins")
async def a_admins(c):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c)
    kb=[]
    if allowed(c.from_user.id,"owner","senior_admin"): kb.append([InlineKeyboardButton(text="➕ Добавить администратора",callback_data="a:admadd")])
    kb += [[InlineKeyboardButton(text="📋 Список администраторов",callback_data="a:admlist")],[InlineKeyboardButton(text="✏️ Изменить роль",callback_data="a:admrole")],[InlineKeyboardButton(text="🗑 Удалить администратора",callback_data="a:admdel")],[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:home")]]
    await edit(c,"👥 <b>Администраторы</b>",InlineKeyboardMarkup(inline_keyboard=kb))
@dp.callback_query(F.data=="a:admlist")
async def admins_list(c):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c); rows=await db_fetchall("SELECT a.user_id,a.role,u.name,u.username FROM administrators a LEFT JOIN users u ON u.id=a.user_id ORDER BY CASE a.role WHEN 'owner' THEN 0 WHEN 'senior_admin' THEN 1 ELSE 2 END,a.user_id")
    body="\n\n".join(f"<b>{ROLE_NAME[r['role']]}</b>\n👤 {esc(r['name'] or 'Неизвестно')}\n💬 @{esc(r['username'] or 'нет')}\n🆔 <code>{r['user_id']}</code>" for r in rows) or "Список пуст."
    await edit(c,"📋 <b>Список администраторов</b>\n\n"+body,InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:admins")]]))
@dp.callback_query(F.data=="a:admadd")
async def admin_add(c,state):
    if not await require(c,"owner","senior_admin"): return
    await answer_callback(c); await state.set_state(AdminAdd.user_id); await edit(c,"Введите Telegram ID нового администратора:")
@dp.message(AdminAdd.user_id)
async def admin_add_id(m,state):
    if not allowed(m.from_user.id,"owner","senior_admin"): return
    try: uid=int((m.text or '').strip()); assert uid>0
    except (ValueError,AssertionError): return await m.answer("Введите корректный числовой Telegram ID.")
    if uid==m.from_user.id: return await m.answer("Нельзя изменить свою роль этим способом.")
    await state.update_data(target_id=uid); await state.set_state(AdminAdd.role)
    roles=[("admin","Admin")] if allowed(m.from_user.id,"senior_admin") else [("senior_admin","Senior Admin"),("admin","Admin")]
    await m.answer("Выберите роль:",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name,callback_data="a:setrole:"+role)] for role,name in roles]))
@dp.callback_query(F.data.startswith("a:setrole:"))
async def admin_set_role(c,state):
    if not await require(c,"owner","senior_admin"): return
    role=c.data.rsplit(":",1)[1]; d=await state.get_data()
    if role not in ROLES or (role=="owner") or (allowed(c.from_user.id,"senior_admin") and role!="admin"): return await answer_callback(c,"Недостаточно прав",True)
    uid=d.get("target_id")
    if not isinstance(uid,int): return await answer_callback(c,"Сессия истекла",True)
    old=role_of(uid)
    if old and not can_manage_admin(c.from_user.id,old): return await answer_callback(c,"Этого администратора нельзя изменить",True)
    await answer_callback(c); await db_execute("INSERT INTO administrators(user_id,role,added_by) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET role=excluded.role,added_by=excluded.added_by",(uid,role,c.from_user.id)); await refresh_caches(); await state.clear(); await c.message.answer("✅ Администратор сохранён.",reply_markup=admin_kb(c.from_user.id))
async def choose_admin_target(c, mode):
    rows=await db_fetchall("SELECT user_id,role FROM administrators ORDER BY user_id")
    rows=[r for r in rows if can_manage_admin(c.from_user.id,r['role'])]
    if not rows: return await answer_callback(c,"Нет доступных администраторов",True)
    await answer_callback(c); await edit(c,"Выберите администратора:",InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{ROLE_NAME[r['role']]} — {r['user_id']}",callback_data=f"a:{mode}:{r['user_id']}")] for r in rows]+[[InlineKeyboardButton(text="⬅️ Назад",callback_data="a:admins")]]))
@dp.callback_query(F.data=="a:admrole")
async def admin_role_choose(c):
    if await require(c,"owner","senior_admin"): await choose_admin_target(c,"rolepick")
@dp.callback_query(F.data=="a:admdel")
async def admin_delete_choose(c):
    if await require(c,"owner","senior_admin"): await choose_admin_target(c,"delpick")
@dp.callback_query(F.data.startswith("a:rolepick:"))
async def role_pick(c):
    if not await require(c,"owner","senior_admin"): return
    try: uid=int(c.data.rsplit(":",1)[1])
    except ValueError:return
    target=role_of(uid)
    if not target or not can_manage_admin(c.from_user.id,target): return await answer_callback(c,"Недостаточно прав",True)
    await answer_callback(c); roles=[("admin","Admin")] if allowed(c.from_user.id,"senior_admin") else [("senior_admin","Senior Admin"),("admin","Admin")]
    await edit(c,"Выберите новую роль:",InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=name,callback_data=f"a:changerole:{uid}:{role}")] for role,name in roles]))
@dp.callback_query(F.data.startswith("a:changerole:"))
async def change_role(c):
    if not await require(c,"owner","senior_admin"):return
    p=c.data.split(":")
    try: uid=int(p[2]); new=p[3]
    except (ValueError,IndexError):return
    old=role_of(uid)
    if new not in ("admin","senior_admin") or not old or not can_manage_admin(c.from_user.id,old) or (allowed(c.from_user.id,"senior_admin") and new!="admin"): return await answer_callback(c,"Недостаточно прав",True)
    await answer_callback(c); await db_execute("UPDATE administrators SET role=? WHERE user_id=?",(new,uid)); await refresh_caches(); await c.message.answer("✅ Роль изменена.")
@dp.callback_query(F.data.startswith("a:delpick:"))
async def delete_admin(c):
    if not await require(c,"owner","senior_admin"):return
    try:uid=int(c.data.rsplit(":",1)[1])
    except ValueError:return
    role=role_of(uid)
    if not role or not can_manage_admin(c.from_user.id,role): return await answer_callback(c,"Owner удалить нельзя",True)
    await answer_callback(c); await db_execute("DELETE FROM administrators WHERE user_id=?",(uid,)); await refresh_caches(); await c.message.answer("✅ Администратор удалён.")

@dp.errors()
async def errors(event):
    log.exception("Unhandled update error",exc_info=event.exception)
    return True
async def main():
    await initialise()
    await dp.start_polling(bot)
if __name__ == "__main__": asyncio.run(main())
