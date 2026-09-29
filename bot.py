import os, asyncio, sqlite3, logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logging.basicConfig(level=logging.INFO)
TOKEN=os.getenv('BOT_TOKEN','')
ADMIN_ID=int(os.getenv('ADMIN_ID','0'))
if not TOKEN: raise RuntimeError('BOT_TOKEN is not set')
bot=Bot(TOKEN); dp=Dispatcher()
DB=os.getenv('DB_PATH','data/zyveron.db'); os.makedirs(os.path.dirname(DB) or '.',exist_ok=True)
conn=sqlite3.connect(DB,check_same_thread=False); conn.row_factory=sqlite3.Row
conn.executescript('''
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, lang TEXT DEFAULT 'ru');
CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, description TEXT, price TEXT, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, user_id INTEGER, name TEXT, username TEXT, lang TEXT, text TEXT, contact TEXT, status TEXT DEFAULT 'new', created TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS portfolio(id INTEGER PRIMARY KEY AUTOINCREMENT, file_id TEXT, caption TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP);
''')
def setting(k,d=''): 
 r=conn.execute('SELECT v FROM settings WHERE k=?',(k,)).fetchone(); return r['v'] if r else d
def set_setting(k,v): conn.execute('INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v',(k,v)); conn.commit()
def seed():
 if conn.execute('SELECT COUNT(*) c FROM services').fetchone()['c']==0:
  for n,d,p in [('Telegram-бот','Боты для заявок, заказов и автоматизации','от €50'),('Автоматизация','Автоматизация процессов бизнеса','от €75'),('Сайт','Лендинг или сайт под задачу','от €100'),('Настройка Telegram','Группы, меню, модерация','от €20')]: conn.execute('INSERT INTO services(name,description,price) VALUES(?,?,?)',(n,d,p))
  conn.commit()
seed()

T={'ru':{'choose':'Выберите язык:','welcome':'👋 Добро пожаловать в <b>ZYVERON</b>!\n\nЦифровые решения для бизнеса.','services':'🛠 Услуги','prices':'💰 Цены','portfolio':'🖼 Портфолио','order':'📝 Заказать','contact':'📞 Связаться','language':'🌐 Язык','back':'⬅️ Назад','sent':'✅ Отправлено! Ожидайте ответа от ZYVERON.','ask':'Напишите сообщение одним текстом:','admin':'🔐 Админ-панель'},'lv':{'choose':'Izvēlieties valodu:','welcome':'👋 Laipni lūdzam <b>ZYVERON</b>!\n\nDigitālie risinājumi uzņēmumiem.','services':'🛠 Pakalpojumi','prices':'💰 Cenas','portfolio':'🖼 Portfolio','order':'📝 Pasūtīt','contact':'📞 Sazināties','language':'🌐 Valoda','back':'⬅️ Atpakaļ','sent':'✅ Nosūtīts! Gaidiet ZYVERON atbildi.','ask':'Uzrakstiet ziņu vienā tekstā:','admin':'🔐 Admin panelis'},'en':{'choose':'Choose language:','welcome':'👋 Welcome to <b>ZYVERON</b>!\n\nDigital solutions for business.','services':'🛠 Services','prices':'💰 Prices','portfolio':'🖼 Portfolio','order':'📝 Order','contact':'📞 Contact','language':'🌐 Language','back':'⬅️ Back','sent':'✅ Sent! Please wait for a reply from ZYVERON.','ask':'Write your message in one text:','admin':'🔐 Admin panel'}}
def lang(uid):
 r=conn.execute('SELECT lang FROM users WHERE id=?',(uid,)).fetchone(); return r['lang'] if r else 'ru'
def ensure_user(uid): conn.execute('INSERT OR IGNORE INTO users(id) VALUES(?)',(uid,)); conn.commit()
def kb(uid):
 l=lang(uid); x=T[l]; return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=x['services'],callback_data='services'),InlineKeyboardButton(text=x['prices'],callback_data='prices')],[InlineKeyboardButton(text=x['portfolio'],callback_data='portfolio')],[InlineKeyboardButton(text=x['order'],callback_data='order'),InlineKeyboardButton(text=x['contact'],callback_data='contact')],[InlineKeyboardButton(text=x['language'],callback_data='language')]])
def back(uid): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=T[lang(uid)]['back'],callback_data='home')]])
def admin_kb(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💰 Цены',callback_data='a_prices')],[InlineKeyboardButton(text='🛠 Услуги',callback_data='a_services')],[InlineKeyboardButton(text='📝 Заявки',callback_data='a_requests')],[InlineKeyboardButton(text='🖼 Портфолио',callback_data='a_portfolio')],[InlineKeyboardButton(text='✏️ Тексты/контакты',callback_data='a_texts')]])
state={}
def is_admin(m): return m.from_user.id==ADMIN_ID
@dp.message(CommandStart())
async def start(m):
 ensure_user(m.from_user.id); r=conn.execute('SELECT lang FROM users WHERE id=?',(m.from_user.id,)).fetchone()
 if r and r['lang']!='ru' and setting('lang_set_'+str(m.from_user.id),'')=='1': await m.answer(T[r['lang']]['welcome'],reply_markup=kb(m.from_user.id),parse_mode='HTML'); return
 await m.answer('🌐 <b>'+T['ru']['choose']+'</b>',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🇷🇺 Русский',callback_data='set_ru'),InlineKeyboardButton(text='🇱🇻 Latviešu',callback_data='set_lv')],[InlineKeyboardButton(text='🇬🇧 English',callback_data='set_en')]]),parse_mode='HTML')
@dp.callback_query(F.data.startswith('set_'))
async def setlang(c):
 l=c.data[-2:]; ensure_user(c.from_user.id); conn.execute('UPDATE users SET lang=? WHERE id=?',(l,c.from_user.id)); conn.commit(); set_setting('lang_set_'+str(c.from_user.id),'1'); await c.message.edit_text(T[l]['welcome'],reply_markup=kb(c.from_user.id),parse_mode='HTML'); await c.answer()
@dp.callback_query(F.data=='home')
async def home(c): await c.message.edit_text(T[lang(c.from_user.id)]['welcome'],reply_markup=kb(c.from_user.id),parse_mode='HTML'); await c.answer()
@dp.callback_query(F.data=='language')
async def language(c): await c.message.edit_text(T[lang(c.from_user.id)]['choose'],reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🇷🇺 Русский',callback_data='set_ru'),InlineKeyboardButton(text='🇱🇻 Latviešu',callback_data='set_lv')],[InlineKeyboardButton(text='🇬🇧 English',callback_data='set_en')]])); await c.answer()
@dp.callback_query(F.data=='services')
async def services(c):
 rows=conn.execute('SELECT * FROM services WHERE active=1').fetchall(); text=T[lang(c.from_user.id)]['services']+'\n\n'+'\n\n'.join(f"<b>{r['name']}</b>\n{r['description']}" for r in rows) or 'Пока нет услуг.'; await c.message.edit_text(text,reply_markup=back(c.from_user.id),parse_mode='HTML'); await c.answer()
@dp.callback_query(F.data=='prices')
async def prices(c):
 rows=conn.execute('SELECT * FROM services WHERE active=1').fetchall(); text='💰 <b>'+T[lang(c.from_user.id)]['prices']+'</b>\n\n'+'\n'.join(f"• {r['name']} — <b>{r['price']}</b>" for r in rows); await c.message.edit_text(text,reply_markup=back(c.from_user.id),parse_mode='HTML'); await c.answer()
@dp.callback_query(F.data=='portfolio')
async def portfolio(c):
 rows=conn.execute('SELECT * FROM portfolio ORDER BY id DESC LIMIT 10').fetchall()
 if not rows: await c.message.edit_text('🖼 <b>Портфолио</b>\n\nПока нет работ.',reply_markup=back(c.from_user.id),parse_mode='HTML')
 else:
  for r in rows: await bot.send_photo(c.from_user.id,r['file_id'],caption=r['caption'] or '')
  await c.message.edit_text('🖼 <b>Портфолио</b>',reply_markup=back(c.from_user.id),parse_mode='HTML')
 await c.answer()
@dp.callback_query(F.data.in_({'contact','order'}))
async def form_start(c):
 state[c.from_user.id]={'kind':c.data,'step':'text'}; await c.message.edit_text('📝 '+T[lang(c.from_user.id)]['ask'],reply_markup=back(c.from_user.id)); await c.answer()
@dp.message()
async def text_message(m:Message):
 uid=m.from_user.id
 if uid==ADMIN_ID and uid in state:
  s=state[uid]; act=s.get('admin_action')
  if act:
   if act.startswith('price:'): conn.execute('UPDATE services SET price=? WHERE id=?',(m.text, int(act.split(':')[1]))); conn.commit(); state.pop(uid); await m.answer('✅ Цена обновлена.',reply_markup=admin_kb()); return
   if act.startswith('name:'): conn.execute('UPDATE services SET name=? WHERE id=?',(m.text,int(act.split(':')[1]))); conn.commit(); state.pop(uid); await m.answer('✅ Название обновлено.',reply_markup=admin_kb()); return
   if act.startswith('desc:'): conn.execute('UPDATE services SET description=? WHERE id=?',(m.text,int(act.split(':')[1]))); conn.commit(); state.pop(uid); await m.answer('✅ Описание обновлено.',reply_markup=admin_kb()); return
   if act=='contact': set_setting('contact',m.text); state.pop(uid); await m.answer('✅ Контакт сохранён.',reply_markup=admin_kb()); return
  if s.get('admin_new_service'):
   parts=m.text.split('|',2)
   if len(parts)==3: conn.execute('INSERT INTO services(name,description,price) VALUES(?,?,?)',tuple(x.strip() for x in parts)); conn.commit(); state.pop(uid); await m.answer('✅ Услуга добавлена. Формат: название | описание | цена',reply_markup=admin_kb()); return
 if uid in state and state[uid].get('kind') in ('contact','order'):
  s=state.pop(uid); contact=m.from_user.username or str(uid); rid=conn.execute('INSERT INTO requests(kind,user_id,name,username,lang,text,contact) VALUES(?,?,?,?,?,?,?)',(s['kind'],uid,m.from_user.full_name,m.from_user.username,lang(uid),m.text,contact)).lastrowid; conn.commit()
  if ADMIN_ID: await bot.send_message(ADMIN_ID,f"🆕 <b>Новая {'заявка' if s['kind']=='order' else 'связь'} #{rid}</b>\n👤 {m.from_user.full_name}\n🆔 <code>{uid}</code>\n💬 @{m.from_user.username or 'нет'}\n🌐 {lang(uid)}\n\n{m.text}",parse_mode='HTML')
  await m.answer(T[lang(uid)]['sent']); await m.answer(T[lang(uid)]['welcome'],reply_markup=kb(uid),parse_mode='HTML'); return
 if uid==ADMIN_ID: await m.answer('Используйте /admin')

@dp.message(F.photo)
async def photo_admin(m):
 if m.from_user.id==ADMIN_ID and state.get(m.from_user.id,{}).get('admin_new_photo'):
  cap=m.caption or ''; conn.execute('INSERT INTO portfolio(file_id,caption) VALUES(?,?)',(m.photo[-1].file_id,cap)); conn.commit(); state.pop(m.from_user.id); await m.answer('✅ Работа добавлена в портфолио.',reply_markup=admin_kb())
@dp.message(commands=['admin'])
async def admin_cmd(m):
 if not is_admin(m): return
 await m.answer('🔐 <b>ZYVERON Admin</b>\n\nВыберите раздел:',reply_markup=admin_kb(),parse_mode='HTML')
@dp.callback_query(F.data.startswith('a_'))
async def admin_menu(c):
 if c.from_user.id!=ADMIN_ID: return await c.answer('Нет доступа',show_alert=True)
 a=c.data
 if a=='a_prices' or a=='a_services':
  rows=conn.execute('SELECT * FROM services ORDER BY id').fetchall(); buttons=[[InlineKeyboardButton(text=f"{r['name']} | {r['price']}",callback_data=f"edit:{r['id']}")] for r in rows]
  buttons.append([InlineKeyboardButton(text='➕ Добавить услугу',callback_data='new_service')]); buttons.append([InlineKeyboardButton(text='⬅️ Админ-меню',callback_data='admin')]); await c.message.edit_text('🛠 <b>Услуги и цены</b>\n\nНажмите на услугу для редактирования.',reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),parse_mode='HTML')
 elif a=='a_requests':
  rows=conn.execute("SELECT * FROM requests WHERE status='new' ORDER BY id DESC LIMIT 20").fetchall(); text='📝 <b>Новые заявки</b>\n\n'+('\n'.join(f"#{r['id']} • {r['name']} • {r['kind']}\n{r['text'][:100]}" for r in rows) if rows else 'Нет новых заявок.'); await c.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='⬅️ Админ-меню',callback_data='admin')]]),parse_mode='HTML')
 elif a=='a_portfolio': await c.message.edit_text('🖼 <b>Портфолио</b>\n\nНажмите «Добавить» и отправьте фотографию с подписью.',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='➕ Добавить фото',callback_data='new_photo')],[InlineKeyboardButton(text='⬅️ Админ-меню',callback_data='admin')]]),parse_mode='HTML')
 elif a=='a_texts': await c.message.edit_text(f"✏️ <b>Тексты и контакты</b>\n\nТекущий контакт: {setting('contact','не задан')}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📞 Изменить контакт',callback_data='edit_contact')],[InlineKeyboardButton(text='⬅️ Админ-меню',callback_data='admin')]]),parse_mode='HTML')
 await c.answer()
@dp.callback_query(F.data=='admin')
async def admin_back(c):
 if c.from_user.id==ADMIN_ID: await c.message.edit_text('🔐 <b>ZYVERON Admin</b>',reply_markup=admin_kb(),parse_mode='HTML')
 await c.answer()
@dp.callback_query(F.data.startswith('edit:'))
async def edit_service(c):
 if c.from_user.id!=ADMIN_ID:return
 sid=int(c.data.split(':')[1]); r=conn.execute('SELECT * FROM services WHERE id=?',(sid,)).fetchone();
 kb2=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💰 Изменить цену',callback_data=f'price:{sid}')],[InlineKeyboardButton(text='✏️ Изменить название',callback_data=f'name:{sid}')],[InlineKeyboardButton(text='📝 Изменить описание',callback_data=f'desc:{sid}')],[InlineKeyboardButton(text='⬅️ Назад',callback_data='a_services')]])
 await c.message.edit_text(f"<b>{r['name']}</b>\nЦена: {r['price']}\nОписание: {r['description']}",reply_markup=kb2,parse_mode='HTML'); await c.answer()
@dp.callback_query(F.data.startswith(('price:','name:','desc:')))
async def edit_field(c):
 if c.from_user.id!=ADMIN_ID:return
 act,sid=c.data.split(':'); state[c.from_user.id]={'admin_action':f'{act}:{sid}'}; labels={'price':'цену','name':'название','desc':'описание'}; await c.message.answer(f'Введите новое значение для {labels[act]}.'); await c.answer()
@dp.callback_query(F.data=='new_service')
async def new_service(c): state[c.from_user.id]={'admin_new_service':True}; await c.message.answer('Отправьте: название | описание | цена\nНапример: Бот для магазина | Заказы и уведомления | от €100'); await c.answer()
@dp.callback_query(F.data=='new_photo')
async def new_photo(c): state[c.from_user.id]={'admin_new_photo':True}; await c.message.answer('Отправьте фотографию. В подписи можно написать описание работы.'); await c.answer()
@dp.callback_query(F.data=='edit_contact')
async def edit_contact(c): state[c.from_user.id]={'admin_action':'contact'}; await c.message.answer('Введите новый контакт, например @zyveron или ссылку.'); await c.answer()

async def main(): await dp.start_polling(bot)
if __name__=='__main__': asyncio.run(main())
