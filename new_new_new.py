#Работающий бот со статистикой, опробованный на render+
#АПГРЕЙД ТАРИФА

import os
import telebot
import sqlite3
import threading
import atexit
from datetime import datetime
import time
import schedule
from flask import Flask
import logging
# ДОБАВЬТЕ ЭТУ СТРОКУ В САМОМ НАЧАЛЕ ФАЙЛА:
from flask import request  # <-- это очень важно!

# ========== НАСТРОЙКА ЛОГГИРОВАНИЯ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ========== ВЕБ-СЕРВЕР ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return "🎨 Пленэрный Клуб Бот работает!"

@app.route('/health')
def health():
    return "OK", 200

# ======= ВЕБХУК ДЛЯ TELEGRAM =======
@app.route('/webhook', methods=['POST'])  # ИСПРАВЛЕННАЯ СТРОКА
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    from flask import request
    
    # Проверяем токен для безопасности
    token = request.headers.get('X-Telegram-Bot-Token') or request.args.get('token')
    
    if token != BOT_TOKEN:
        return 'Unauthorized', 401
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ====================================

# Запускаем Flask в отдельном потоке
def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# Запускаем Flask в отдельном потоке
def run_flask():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8432420548:AAGX_EqsarA7q_Jx4iNL2zV8j3c_JWd_POU"
CHANNEL_ID = "-1003227241488"  # Твой канал
ADMIN_ID = 644037215  # Твой ID
TILDA_LINK = "https://pleinairclub.tilda.ws/"  # Ссылка на Tilda

# ТВОИ РЕКВИЗИТЫ ДЛЯ ОПЛАТЫ
SBER_PHONE = "+79043323607"  # Твой номер телефона Сбер
SBER_CARD = "2202208262152375"  # Твоя карта Сбер (если есть)
YOUR_NAME = "Илья Козлов"  # Твое имя для перевода

# Путь к базе данных
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'club.db')
logger.info(f"📁 Путь к БД: {DB_PATH}")

# ========== ИНИЦИАЛИЗАЦИЯ БОТА ==========
bot = telebot.TeleBot(BOT_TOKEN)

# ========== РАБОТА С БАЗОЙ ДАННЫХ ==========
thread_local = threading.local()

def get_db_connection():
    """Создает соединение с БД для текущего потока"""
    try:
        if not hasattr(thread_local, "conn") or thread_local.conn is None:
            logger.info("🔌 Создаем новое соединение с БД")
            thread_local.conn = sqlite3.connect(
                DB_PATH, 
                check_same_thread=False,
                timeout=10
            )
            thread_local.cursor = thread_local.conn.cursor()
            
            # Оптимизация для SQLite
            thread_local.conn.execute("PRAGMA journal_mode=WAL")
            thread_local.conn.execute("PRAGMA synchronous=NORMAL")
            thread_local.conn.execute("PRAGMA foreign_keys=ON")
            
            # Создаем таблицы
            create_tables()
        
        return thread_local.conn, thread_local.cursor
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        raise
        
def check_database_structure():
    """Проверяет и исправляет структуру базы данных (вызывается один раз при старте)"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Проверяем наличие всех колонок в таблице users
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Список необходимых колонок
        required_columns = [
            ('user_id', 'INTEGER PRIMARY KEY'),
            ('tariff', 'TEXT'),
            ('amount', 'INTEGER DEFAULT 0'),
            ('clicked_link', 'INTEGER DEFAULT 0'),
            ('paid', 'INTEGER DEFAULT 0'),
            ('purchase_date', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
            ('screenshot_date', 'TIMESTAMP'),
            ('updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ]
        
        # Проверяем каждую колонку
        for col_name, col_type in required_columns:
            if col_name not in columns:
                logger.warning(f"➕ Добавляем колонку {col_name} в таблицу users")
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                except Exception as e:
                    logger.error(f"❌ Не удалось добавить колонку {col_name}: {e}")
        
        conn.commit()
        conn.close()
        logger.info("✅ Структура базы данных проверена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки структуры БД: {e}")

def create_tables():
    """Создает таблицы с правильной структурой"""
    cursor = thread_local.cursor
    
    # Таблица пользователей - ТОЛЬКО CREATE IF NOT EXISTS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            tariff TEXT,
            amount INTEGER DEFAULT 0,
            clicked_link INTEGER DEFAULT 0,
            paid INTEGER DEFAULT 0,
            purchase_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            screenshot_date TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица сообщений в канале
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_messages (
            message_id INTEGER PRIMARY KEY,
            user_id INTEGER,
            first_name TEXT,
            username TEXT,
            text TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            tariff TEXT,
            FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
        )
    ''')
    
    # Создаем индексы для ускорения запросов
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_paid ON users(paid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_tariff ON users(tariff)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_date ON channel_messages(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user ON channel_messages(user_id)")
    
    thread_local.conn.commit()
    logger.info("✅ Таблицы созданы/проверены")

# ========== КОМАНДА /START ==========
@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"🚀 Команда /start от {message.from_user.id}")
    
    # Первое приветственное сообщение
    bot.send_message(
        message.chat.id,
        "Приветствую Вас. Оставайтесь на волне созерцания и пленэра!"
    )
    
    # ОТПРАВКА ФОТОГРАФИИ
    try:
        # Здесь нужно указать путь к вашей фотографии
        # Вариант 1: Если фото лежит в интернете (ссылка)
        # photo_url = "https://example.com/your-photo.jpg"
        # bot.send_photo(message.chat.id, photo_url)
        
        # Вариант 2: Если фото лежит в той же папке на Render
        with open('your-photo.jpg', 'rb') as photo:
            bot.send_photo(message.chat.id, photo)
            
        logger.info(f"📸 Фотография отправлена пользователю {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке фото: {e}")
        # Если фото не отправилось, можно отправить сообщение об этом
        bot.send_message(
            message.chat.id,
            "К сожалению, не удалось загрузить фотографию 😔"
        )
    
    # Второе сообщение с описанием и кнопками
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    btn_more = telebot.types.InlineKeyboardButton(
        text="Узнать больше",
        url=TILDA_LINK
    )
    
    btn_club = telebot.types.InlineKeyboardButton(
        text="Хочу в клуб!",
        callback_data="join_club"
    )
    
    markup.add(btn_more, btn_club)
    
    bot.send_message(
        message.chat.id,
        "Здесь можно купить подписку и получить доступ в \"Пленэрный Клуб\"!\n\n"
        "Это закрытый телеграм-канал, где все участники могут делиться своим творчеством и получать от меня обратную связь. "
        "Также на канале будет много эксклюзивных видео-уроков и другие полезные материалы, которые я обычно выкладываю на платной основе.\n\n"
        "Здесь Вы получите мою профессиональную поддержку и сможете более уверенно шагать по пути искусства!",
        reply_markup=markup,
        parse_mode=None
    )
# ========== ПРЕДЛОЖЕНИЕ КЛУБА ==========
@bot.callback_query_handler(func=lambda call: call.data == "join_club")
def show_club_offer(call):
    logger.info(f"🎯 Показываем предложение клуба для {call.from_user.id}")
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    
    btn_reader = telebot.types.InlineKeyboardButton(
        text="🔥 ЧИТАТЕЛЬ — 100₽/месяц",
        callback_data="tariff_reader"
    )
    btn_member = telebot.types.InlineKeyboardButton(
        text="💎 УЧАСТНИК — 500₽/месяц", 
        callback_data="tariff_member"
    )
    
    markup.add(btn_reader, btn_member)
    
    bot.send_message(
        call.from_user.id,
        "🎯 ВЫБЕРИТЕ ТАРИФ ДОСТУПА К ПЛЕНЭРНОМУ КЛУБУ:\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔥 ЧИТАТЕЛЬ — 100₽\n"
        "• Просмотр всех материалов канала\n"
        "• Доступ к архиву постов\n"
        "• Без обратной связи\n\n"
        "💎 УЧАСТНИК — 500₽\n"  
        "• Всё из тарифа Читатель\n"
        "• Разбор Ваших работ\n"
        "• Помощь по всем творческим вопросам\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 ВЫБЕРИТЕ ТАРИФ И НАЖМИТЕ КНОПКУ",
        reply_markup=markup,
        parse_mode=None
    )

@bot.callback_query_handler(func=lambda call: call.data in ["tariff_reader", "tariff_member"])
def handle_tariff_selection(call):
    user_id = call.from_user.id
    logger.info(f"💎 Выбор тарифа {call.data} от {user_id}")
    
    # ОТЛАДОЧНЫЙ ВЫВОД - ДОБАВЬ ЭТИ СТРОКИ
    print("=" * 50)
    print(f"🔍 ОТЛАДКА: Начало обработки выбора тарифа")
    print(f"🔍 Пользователь ID: {user_id}")
    print(f"🔍 Выбран тариф: {call.data}")
    print("=" * 50)
    
    if call.data == "tariff_reader":
        tariff = "читатель"
        amount = 100
    else:
        tariff = "участник" 
        amount = 500
    
    try:
        conn, cursor = get_db_connection()
        
        # Проверяем, есть ли пользователь в базе
        cursor.execute("SELECT tariff, paid FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        
        # ОТЛАДОЧНЫЙ ВЫВОД - ДОБАВЬ ЭТИ СТРОКИ
        print(f"🔍 Результат запроса к БД: {user_data}")
        print(f"🔍 Тип результата: {type(user_data)}")
        if user_data is not None:
            print(f"🔍 Длина кортежа: {len(user_data)}")
            print(f"🔍 Содержимое: tariff={user_data[0]}, paid={user_data[1]}")
        else:
            print("🔍 Результат: None (пользователь не найден)")
        
        # ИСПРАВЛЕНИЕ: ПРАВИЛЬНАЯ ПРОВЕРКА
        if user_data is not None and len(user_data) == 2:
            # Теперь безопасно распаковываем
            current_tariff, paid = user_data
            
            print(f"🔍 Успешно распаковано: current_tariff='{current_tariff}', paid={paid}")
            
            # Если уже оплатил - предлагаем апгрейд
            if paid:
                print(f"🔍 Пользователь уже оплатил! paid={paid}")
                
                if current_tariff == "читатель" and tariff == "участник":
                    # Предлагаем апгрейд
                    markup = telebot.types.InlineKeyboardMarkup()
                    btn_upgrade = telebot.types.InlineKeyboardButton(
                        "💎 ПЕРЕЙТИ (доплатить 400₽)",
                        callback_data="upgrade_to_member"
                    )
                    markup.add(btn_upgrade)
                    
                    bot.send_message(
                        user_id,
                        f"✅ Вы уже оплатили тариф '{current_tariff.upper()}'!\n\n"
                        f"Хотите перейти на 'УЧАСТНИКА'?\n"
                        f"К доплате: {amount - 100}₽",
                        reply_markup=markup,
                        parse_mode=None
                    )
                    return
                else:
                    bot.answer_callback_query(call.id, f"✅ Вы уже на тарифе {current_tariff.upper()}")
                    return
        else:
            # Пользователя нет в базе или данные некорректны
            print(f"🔍 Пользователь {user_id} не найден в базе или данные некорректны")
            logger.info(f"👤 Пользователь {user_id} не найден в базе")
        
        # ЕСЛИ ПОЛЬЗОВАТЕЛЯ НЕТ В БАЗЕ ИЛИ НЕ ОПЛАЧИВАЛ - создаем/обновляем запись
        print(f"🔍 Создаем/обновляем запись для пользователя {user_id}")
        
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, tariff, amount, clicked_link, updated_at) 
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
        """, (user_id, tariff, amount))
        
        conn.commit()
        
        bot.answer_callback_query(call.id, f"Вы выбрали {tariff}")
        
        # Текст с реквизитами
        message_text = f"""Вы выбрали тариф: {tariff.upper()}

Сумма к оплате: {amount} рублей

ПРОСТОЙ СПОСОБ ОПЛАТЫ:

1. Переведите {amount} рублей на номер:
{SBER_PHONE}"""
        
        if SBER_CARD:
            message_text += f"""

Или на карту: {SBER_CARD}"""
        
        message_text += f"""

2. Отправьте скриншот перевода в этот чат

Доступ к каналу откроется автоматически!

Если возникнут проблемы, напишите мне @artistilja"""
        
        bot.send_message(user_id, message_text, parse_mode=None)
        
        # Уведомление админу
        bot.send_message(
            ADMIN_ID,
            f"НОВЫЙ ВЫБОР ТАРИФА\n\n"
            f"Пользователь: {call.from_user.first_name}\n"
            f"Username: @{call.from_user.username or 'без username'}\n"
            f"ID: {user_id}\n\n"
            f"Тариф: {tariff.upper()}\n"
            f"Сумма: {amount}₽\n\n"
            f"Ожидает оплаты (скриншот)",
            parse_mode=None
        )
        
        logger.info(f"✅ Тариф {tariff} сохранен для {user_id}")
        
    except Exception as e:
        print(f"🔍 ❌ ОШИБКА в функции: {e}")
        import traceback
        print(f"🔍 Детали ошибки:\n{traceback.format_exc()}")
        
        logger.error(f"❌ Ошибка при выборе тарифа: {e}")
        logger.error(f"Детали ошибки: {traceback.format_exc()}")
        bot.answer_callback_query(call.id, "Ошибка, попробуйте еще раз")
        
#============АПГРЕЙД ТАРИФА=====

@bot.callback_query_handler(func=lambda call: call.data == "upgrade_to_member")
def handle_upgrade(call):
    """Обработка апгрейда с читателя на участника"""
    user_id = call.from_user.id
    logger.info(f"⬆️ Запрос на апгрейд от {user_id}")
    
    conn, cursor = get_db_connection()
    
    # Получаем текущий тариф
    cursor.execute("SELECT tariff, amount FROM users WHERE user_id = ?", (user_id,))
    current_data = cursor.fetchone()
    
    if not current_data or current_data[0] != "читатель":
        bot.answer_callback_query(call.id, "❌ Нельзя выполнить апгрейд")
        return
    
    old_tariff, old_amount = current_data
    new_tariff = "участник"
    new_amount = 500
    to_pay = new_amount - old_amount  # 400₽
    
    # Обновляем тариф (но оставляем paid = 1)
    cursor.execute("""
        UPDATE users 
        SET tariff = ?, amount = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    """, (new_tariff, new_amount, user_id))
    conn.commit()
    
    bot.answer_callback_query(call.id, "✅ Тариф изменен на Участник!")
    
    # Инструкция по доплате
    bot.send_message(
        user_id,
        f"🎉 ВЫ ПЕРЕХОДИТЕ НА ТАРИФ 'УЧАСТНИК'!\n\n"
        f"✅ Ваш новый тариф: {new_tariff.upper()}\n"
        f"💰 К доплате: {to_pay}₽\n\n"
        f"Доплатите {to_pay}₽ на:\n"
        f"📱 {SBER_PHONE}\n\n"
        f"И отправьте скриншот сюда.\n\n"
        f"После доплаты вы получите:\n"
        f"• Обратную связь по Вашим работам\n"
        f"• Возможность задавать вопросы по творчеству и получать поддержку от меня\n",
        parse_mode=None
    )
    
    # Уведомление админу
    bot.send_message(
        ADMIN_ID,
        f"⬆️ ЗАПРОС НА АПГРЕЙД\n\n"
        f"👤 Пользователь: {call.from_user.first_name}\n"
        f"📛 @{call.from_user.username or 'без username'}\n"
        f"🆔 ID: {user_id}\n\n"
        f"📈 С {old_tariff} ({old_amount}₽) → {new_tariff} ({new_amount}₽)\n"
        f"💰 К доплате: {to_pay}₽\n\n"
        f"Ожидает скриншот доплаты",
        parse_mode=None
    )

# ========== ОБРАБОТКА СКРИНШОТОВ ОПЛАТЫ ==========
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    """Автоматическая обработка скриншотов оплаты"""
    user_id = message.from_user.id
    logger.info(f"📸 Получен скриншот от {user_id}")
    
    # Получаем текущие данные пользователя
    conn, cursor = get_db_connection()
    cursor.execute("SELECT tariff, amount, paid FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        # Пользователь еще не выбирал тариф
        bot.send_message(
            user_id,
            "❌ Сначала выберите тариф \n\n"
            "Пожалуйста, вернитесь к сообщению с выбором тарифа и начните оплату оттуда.",
            parse_mode=None
        )
        return
    
    old_tariff, old_amount, already_paid = user_data
    
    # Если уже оплатил - проверяем, не хочет ли апгрейд
    if already_paid:
        # Показываем меню апгрейда
        markup = telebot.types.InlineKeyboardMarkup(row_width=1)
        
        if old_tariff == "читатель":
            btn_upgrade = telebot.types.InlineKeyboardButton(
                text="💎 ПЕРЕЙТИ НА УЧАСТНИКА (доплатить 400₽)",
                callback_data="upgrade_to_member"
            )
            markup.add(btn_upgrade)
            
            bot.send_message(
                user_id,
                f"✅ Вы уже в клубе на тарифе '{old_tariff.upper()}'!\n\n"
                f"Хотите перейти на тариф 'УЧАСТНИК' с обратной связью?\n"
                f"• Ваш текущий тариф: {old_tariff} ({old_amount}₽)\n"
                f"• Новый тариф: участник (500₽)\n"
                f"• К доплате: {500 - old_amount}₽\n\n"
                f"Нажмите кнопку ниже для перехода:",
                reply_markup=markup,
                parse_mode=None
            )
        else:
            # Уже участник - сообщаем
            bot.send_message(
                user_id,
                f"🎉 Вы на максимальном тарифе - 'УЧАСТНИК'!\n\n"
                f"Следующий платеж: через 30 дней от последней оплаты.\n\n"
                f"Если есть вопросы, пишите @artistilja",
                parse_mode=None
            )
        return
    
    # Если не оплачивал - обычная логика
    tariff = old_tariff
    amount = old_amount
    
    # Обновляем статус оплаты
    screenshot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE users 
        SET paid = 1, screenshot_date = ?, updated_at = CURRENT_TIMESTAMP 
        WHERE user_id = ?
    """, (screenshot_time, user_id))
    conn.commit()
    
    # Создаем ссылку-приглашение
    try:
        invite_link = bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            creates_join_request=False
        )
        
        # Отправляем пользователю ссылку на канал
        bot.send_message(
            user_id,
            f"🎉 СКРИНШОТ ПОЛУЧЕН! ДОБРО ПОЖАЛОВАТЬ В КЛУБ!\n\n"
            f"✅ Ваш тариф: {tariff.upper()}\n"
            f"💰 Сумма: {amount}₽\n\n"
            f"Ссылка для перехода: {invite_link.invite_link}\n\n"
            "Если возникнут проблемы с доступом, напишите мне @artistilja\n\n"
            "🎨 Увидимся внутри!",
            parse_mode=None,
            disable_web_page_preview=True
        )
        
        # Уведомляем админа
        bot.send_message(
            ADMIN_ID,
            f"🔄 АВТОМАТИЧЕСКАЯ ВЫДАЧА ДОСТУПА\n\n"
            f"👤 Пользователь: {message.from_user.first_name}\n"
            f"📛 @{message.from_user.username or 'без username'}\n"
            f"🆔 ID: {user_id}\n\n"
            f"💎 Тариф: {tariff}\n"
            f"💵 Сумма: {amount}₽\n\n"
            f"✅ Доступ выдан автоматически по скриншоту\n"
            f"⏰ Время: {screenshot_time}\n\n"
            f"📸 Скриншот ниже (переслан):",
            parse_mode=None
        )
        
        # Пересылаем скриншот админу
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        
        logger.info(f"✅ Доступ выдан {user_id} ({tariff})")
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"❌ Ошибка при выдаче доступа: {error_msg}")
        
        bot.send_message(
            user_id,
            "⏳ Скриншот получен!\n\n"
            "Идет обработка...\n"
            "Если доступ не откроется через минуту, напишите мне @artistilja",
            parse_mode=None
        )
        
        bot.send_message(
            ADMIN_ID,
            f"❌ ОШИБКА АВТОМАТИЧЕСКОЙ ВЫДАЧИ\n\n"
            f"👤 {user_id}\n"
            f"📛 @{message.from_user.username or 'нет'}\n"
            f"💎 Тариф: {tariff}\n\n"
            f"⚠️ Ошибка: {error_msg[:200]}\n\n"
            f"Добавьте пользователя вручную командой:\n"
            f"/add {user_id}\n\n"
            f"📸 Скриншот:",
            parse_mode=None
        )
        
        bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)

#=============КОМАНДА ДЛЯ ПРОВЕРКИ ТАРИФА==============

@bot.message_handler(commands=['mytariff'])
def my_tariff(message):
    """Показать текущий тариф пользователя"""
    user_id = message.from_user.id
    conn, cursor = get_db_connection()
    
    cursor.execute("SELECT tariff, amount, paid, screenshot_date FROM users WHERE user_id = ?", (user_id,))
    user_data = cursor.fetchone()
    
    if not user_data:
        bot.reply_to(message, "❌ Вы еще не выбирали тариф")
        return
    
    tariff, amount, paid, screenshot_date = user_data
    
    status = "✅ ОПЛАЧЕНО" if paid else "⏳ ОЖИДАЕТ ОПЛАТЫ"
    
    response = (
        f"📋 ВАШ ТАРИФ:\n\n"
        f"🎯 Тариф: {tariff.upper() if tariff else 'не выбран'}\n"
        f"💰 Сумма: {amount}₽\n"
        f"📊 Статус: {status}\n"
    )
    
    if paid and screenshot_date:
        response += f"🕒 Оплачено: {screenshot_date}\n"
    
    # Если читатель - предлагаем апгрейд
    if paid and tariff == "читатель":
        markup = telebot.types.InlineKeyboardMarkup()
        btn_upgrade = telebot.types.InlineKeyboardButton(
            "💎 ПЕРЕЙТИ НА УЧАСТНИКА (+400₽)",
            callback_data="upgrade_to_member"
        )
        markup.add(btn_upgrade)
        
        response += f"\n⚠️ На вашем тарифе нет обратной связи\n"
        response += f"Хотите получить разборы работ и ответы на вопросы?"
        
        bot.send_message(user_id, response, reply_markup=markup, parse_mode=None)
    else:
        bot.reply_to(message, response, parse_mode=None)

#=======СБРОС СВОИХ ДАННЫХ ДЛЯ ТЕСТА============

@bot.message_handler(commands=['resetme'])
def reset_user_data(message):
    """Удалить свои данные из базы для тестирования"""
    user_id = message.from_user.id
    
    # Только админ может сбрасывать себя
    if user_id != ADMIN_ID:
        bot.reply_to(message, "❌ Эта команда только для тестирования администратором")
        return
    
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    btn_yes = telebot.types.InlineKeyboardButton("✅ Сбросить меня", callback_data=f"reset_user_{user_id}")
    btn_no = telebot.types.InlineKeyboardButton("❌ Отмена", callback_data="reset_cancel")
    markup.add(btn_yes, btn_no)
    
    bot.send_message(
        message.chat.id,
        "🔄 **СБРОС ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ**\n\n"
        "Это удалит ВАС из базы данных:\n"
        "• Ваш тариф\n"
        "• Статус оплаты\n"
        "• Историю\n\n"
        "После сброса вы сможете:\n"
        "• Пройти регистрацию заново\n"
        "• Выбрать тариф\n"
        "• Протестировать оплату\n\n"
        "Подтвердите действие:",
        reply_markup=markup,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("reset_user_"))
def handle_reset_user(call):
    if call.data == "reset_cancel":
        bot.answer_callback_query(call.id, "❌ Отменено")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return
    
    # Извлекаем ID пользователя из callback_data
    user_id_to_reset = int(call.data.split("_")[2])
    
    try:
        conn, cursor = get_db_connection()
        
        # Удаляем пользователя из базы
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id_to_reset,))
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if deleted > 0:
            bot.answer_callback_query(call.id, "✅ Вы удалены из базы!")
            
            # Обновляем сообщение
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="🎉 **ВЫ УДАЛЕНЫ ИЗ БАЗЫ!**\n\n"
                     "Теперь вы можете:\n"
                     "1. Написать /start\n"
                     "2. Пройти регистрацию заново\n"
                     "3. Протестировать весь процесс\n\n"
                     "✅ База 'забыла' о вас!",
                parse_mode='Markdown'
            )
            
            # Отправляем новое стартовое сообщение
            bot.send_message(
                user_id_to_reset,
                "🔄 **ТЕСТОВЫЙ РЕЖИМ АКТИВЕН**\n\n"
                "Вы были удалены из базы. Теперь можете протестировать бота как новый пользователь!\n\n"
                "Напишите /start чтобы начать.",
                parse_mode='Markdown'
            )
            
            logger.info(f"🔄 Админ {user_id_to_reset} сбросил себя в базе")
        else:
            bot.answer_callback_query(call.id, "❌ Вы и так не в базе")
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="ℹ️ **ВЫ НЕ НАЙДЕНЫ В БАЗЕ**\n\n"
                     "Вы уже удалены или никогда не регистрировались.\n"
                     "Можете сразу писать /start",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"❌ Ошибка сброса пользователя: {e}")
        bot.answer_callback_query(call.id, "❌ Ошибка сброса")

# ========== КОМАНДА /STATS ==========
@bot.message_handler(commands=['stats'])
def show_stats(message):
    """Статистика бота"""
    try:
        logger.info(f"📊 Команда /stats от {message.from_user.id}")
        
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"❌ Отказ: {message.from_user.id} != {ADMIN_ID}")
            bot.send_message(message.chat.id, "❌ Эта команда только для администратора")
            return
        
        logger.info("📈 Начинаем сбор статистики...")
        
        # Получаем соединение с БД
        conn, cursor = get_db_connection()
        logger.info("✅ Соединение с БД установлено")
        
        # Всего пользователей
        cursor.execute("SELECT COUNT(*) FROM users")
        total = cursor.fetchone()[0] or 0
        logger.info(f"👥 Всего пользователей: {total}")
        
        # Получили урок (нажали кнопку)
        cursor.execute("SELECT COUNT(*) FROM users WHERE clicked_link = 1")
        clicked = cursor.fetchone()[0] or 0
        logger.info(f"👀 Получили урок: {clicked}")
        
        # Выбрали тариф
        cursor.execute("SELECT COUNT(*) FROM users WHERE tariff IS NOT NULL AND tariff != ''")
        with_tariff = cursor.fetchone()[0] or 0
        logger.info(f"🎯 Выбрали тариф: {with_tariff}")
        
        # Оплатили
        cursor.execute("SELECT COUNT(*) FROM users WHERE paid = 1")
        paid = cursor.fetchone()[0] or 0
        logger.info(f"💰 Оплатили: {paid}")
        
        # Читатели
        cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(tariff) = 'читатель' AND paid = 1")
        readers = cursor.fetchone()[0] or 0
        logger.info(f"📖 Читатели: {readers}")
        
        # Участники
        cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(tariff) = 'участник' AND paid = 1")
        members = cursor.fetchone()[0] or 0
        logger.info(f"💎 Участники: {members}")
        
        # Общий доход
        cursor.execute("SELECT SUM(amount) FROM users WHERE paid = 1")
        income_result = cursor.fetchone()[0]
        total_income = income_result if income_result is not None else 0
        logger.info(f"💵 Общий доход: {total_income}₽")
        
        # Скриншоты за 7 дней
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE paid = 1 
            AND screenshot_date >= datetime('now', '-7 days')
        """)
        screenshots_7days = cursor.fetchone()[0] or 0
        logger.info(f"📸 Скриншоты (7 дней): {screenshots_7days}")
        
        # Последние оплаты
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE paid = 1 
            AND DATE(updated_at) = DATE('now')
        """)
        today_payments = cursor.fetchone()[0] or 0
        logger.info(f"📅 Оплат сегодня: {today_payments}")
        
        # Закрываем соединение
        conn.close()
        if hasattr(thread_local, "conn"):
            del thread_local.conn
        if hasattr(thread_local, "cursor"):
            del thread_local.cursor
        
        # Формируем статистику
        stats = (
            "📊 *СТАТИСТИКА БОТА*\n\n"
            f"👥 *Всего пользователей:* {total}\n"
            f"🎯 *Выбрали тариф:* {with_tariff}\n"
            f"💰 *Оплатили (в клубе):* {paid}\n"
            f"📖 *Читатели:* {readers}\n"
            f"💎 *Участники:* {members}\n"
            f"💵 *Общий доход:* {total_income}₽\n"
            f"📸 *Скриншоты (7 дней):* {screenshots_7days}\n"
            f"📅 *Оплат сегодня:* {today_payments}\n\n"
        )
        
        # Конверсии
        if total > 0:
            conv_to_tariff = (with_tariff / clicked * 100) if clicked > 0 else 0
            conv_to_paid = (paid / with_tariff * 100) if with_tariff > 0 else 0
            
            stats += "📈 *Конверсия:*\n"
            stats += f"• В тариф: {conv_to_tariff:.1f}%\n"
            stats += f"• В оплату: {conv_to_paid:.1f}%\n\n"
        
        # Добавляем время
        stats += f"🕒 *Время:* {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
        
        # Отправляем
        bot.send_message(message.chat.id, stats, parse_mode='Markdown')
        logger.info("✅ Статистика отправлена успешно")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в /stats: {e}")
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"📋 Детали ошибки:\n{error_details}")
        
        bot.send_message(
            message.chat.id,
            f"❌ Ошибка при получении статистики:\n```{str(e)[:200]}```\n\n"
            "Проверьте логи на Render.",
            parse_mode='Markdown'
        )     

# ========== ТЕСТОВЫЕ КОМАНДЫ ==========

@bot.message_handler(commands=['fullreset'])
def full_reset(message):
    """Полный сброс для тестирования (только админ)"""
    if message.from_user.id != ADMIN_ID:
        return
    
    conn, cursor = get_db_connection()
    
    try:
        # Удаляем ВСЕ свои данные
        cursor.execute("DELETE FROM users WHERE user_id = ?", (ADMIN_ID,))
        cursor.execute("DELETE FROM channel_messages WHERE user_id = ?", (ADMIN_ID,))
        conn.commit()
        
        # Удаляем вебхук (если используется)
        try:
            bot.remove_webhook()
        except:
            pass
        
        bot.reply_to(
            message,
            "🔄 ПОЛНЫЙ СБРОС ВЫПОЛНЕН!\n\n"
            "1. Удалены все ваши данные из базы\n"
            "2. Сброшен вебхук\n"
            "3. Вы полностью 'новый' пользователь\n\n"
            "Напишите /start для начала тестирования."
        )
        
        logger.info(f"🔄 Админ {ADMIN_ID} выполнил полный сброс")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")
        logger.error(f"❌ Ошибка полного сброса: {e}")
        
@bot.message_handler(commands=['ping'])
def ping_command(message):
    """Проверка работы бота"""
    logger.info(f"🏓 Ping от {message.from_user.id}")
    bot.send_message(message.chat.id, "🏓 Pong! Бот работает!")

@bot.message_handler(commands=['check'])
def check_admin(message):
    """Проверка ID пользователя"""
    logger.info(f"🔍 Команда /check от {message.from_user.id}")
    bot.send_message(message.chat.id, f"✅ Команда работает! Ваш ID: {message.from_user.id}")

@bot.message_handler(commands=['testdb'])
def test_database(message):
    """Тест соединения с БД"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        conn, cursor = get_db_connection()
        
        # Проверяем таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        response = "📋 *ТАБЛИЦЫ В БАЗЕ:*\n"
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            response += f"• {table[0]}: {count} записей\n"
        
        # Проверяем пользователей
        cursor.execute("SELECT * FROM users LIMIT 3")
        sample_users = cursor.fetchall()
        
        response += "\n👥 *ПЕРВЫЕ 3 ПОЛЬЗОВАТЕЛЯ:*\n"
        for user in sample_users:
            response += f"• ID: {user[0]}, Тариф: {user[1]}, Оплата: {'✅' if user[4] else '❌'}\n"
        
        conn.close()
        
        bot.send_message(ADMIN_ID, response, parse_mode='Markdown')
        logger.info("✅ Тест БД выполнен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка теста БД: {e}")
        bot.send_message(ADMIN_ID, f"❌ Ошибка БД: {str(e)[:200]}")

# ========== КОМАНДА /LIST ==========
@bot.message_handler(commands=['list'])
def list_users(message):
    """Список всех пользователей"""
    if message.from_user.id == ADMIN_ID:
        conn, cursor = get_db_connection()
        
        try:
            cursor.execute("""
                SELECT user_id, tariff, amount, paid, screenshot_date, updated_at 
                FROM users 
                ORDER BY updated_at DESC 
                LIMIT 20
            """)
            users = cursor.fetchall()
            
            if users:
                response = "📋 *ПОСЛЕДНИЕ 20 ПОЛЬЗОВАТЕЛЕЙ:*\n\n"
                for user_id, tariff, amount, paid, screenshot_date, updated_at in users:
                    status = "✅ ОПЛАЧЕНО" if paid else "⏳ ОЖИДАЕТ"
                    tariff_text = f" • {tariff} ({amount}₽)" if tariff else " • нет тарифа"
                    date_text = f"\n   📅 {updated_at}" if updated_at else ""
                    response += f"• {user_id}: {status}{tariff_text}{date_text}\n"
                    
                    if len(response) > 3500:
                        bot.send_message(ADMIN_ID, response, parse_mode='Markdown')
                        response = ""
            else:
                response = "📭 База пуста"
                
            if response:
                bot.send_message(ADMIN_ID, response, parse_mode='Markdown')
            
            conn.close()
            logger.info("✅ Список пользователей отправлен")
            
        except Exception as e:
            logger.error(f"❌ Ошибка в /list: {e}")
            bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# ========== КОМАНДА /ADD ==========
@bot.message_handler(commands=['add'])
def manual_add_to_channel(message):
    """Ручное добавление пользователя в канал: /add user_id"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        # Получаем ID пользователя из команды
        user_id = int(message.text.split()[1])
        logger.info(f"➕ Ручное добавление пользователя {user_id}")
        
        # Создаем ссылку-приглашение
        invite_link = bot.create_chat_invite_link(
            chat_id=CHANNEL_ID,
            member_limit=1,
            creates_join_request=False
        )
        
        # Отправляем пользователю
        bot.send_message(
            user_id,
            f"🎉 *ВАС ДОБАВИЛИ В ПЛЕНЭРНЫЙ КЛУБ!*\n\n"
            f"👉 [ПЕРЕЙТИ В КЛУБ]({invite_link.invite_link})\n\n"
            "*Ссылка действует 24 часа.*\n"
            "Если ссылка не работает, напишите @artistilja",
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
        # Обновляем статус в базе
        conn, cursor = get_db_connection()
        cursor.execute("UPDATE users SET paid = 1, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        # Получаем информацию о пользователе
        cursor.execute("SELECT tariff, amount FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        tariff_info = f"Тариф: {user_data[0] if user_data else 'неизвестен'}" if user_data else ""
        
        bot.send_message(
            ADMIN_ID, 
            f"✅ Пользователь {user_id} добавлен в канал!\n{tariff_info}"
        )
        
        logger.info(f"✅ Пользователь {user_id} добавлен вручную")
        
    except (IndexError, ValueError):
        bot.send_message(ADMIN_ID, "Используйте: /add USER_ID")
    except Exception as e:
        logger.error(f"❌ Ошибка в /add: {e}")
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {e}")

# ========== ОТСЛЕЖИВАНИЕ СООБЩЕНИЙ В КАНАЛЕ ==========
@bot.message_handler(content_types=['text'])
def handle_channel_messages(message):
    """Сохраняет сообщения из канала"""
    # Проверяем, что сообщение из нужного канала
    if str(message.chat.id) == CHANNEL_ID:
        user_id = message.from_user.id if message.from_user else None
        
        if not user_id:
            return
            
        first_name = message.from_user.first_name if message.from_user else "Аноним"
        username = message.from_user.username if message.from_user and message.from_user.username else None
        
        conn, cursor = get_db_connection()
        
        # Получаем тариф пользователя из базы
        cursor.execute("SELECT tariff FROM users WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        tariff = user_data[0] if user_data else "неизвестен"
        
        # Сохраняем сообщение
        cursor.execute("""
            INSERT OR REPLACE INTO channel_messages 
            (message_id, user_id, first_name, username, text, date, tariff)
            VALUES (?, ?, ?, ?, ?, datetime('now'), ?)
        """, (message.message_id, user_id, first_name, username, message.text, tariff))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"💬 Сообщение сохранено: {first_name} ({tariff}): {message.text[:50]}...")

# ========== ЗАКРЫТИЕ СОЕДИНЕНИЙ ==========
def close_all_connections():
    if hasattr(thread_local, "conn"):
        thread_local.conn.close()
        logger.info("🔌 Все соединения с БД закрыты")

atexit.register(close_all_connections)

# ========== ЗАПУСК БОТА ==========
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🎨 ЗАПУСК ПЛЕНЭРНОГО КЛУБ БОТА")
    logger.info("=" * 50)
    
    check_database_structure()
    
    # НЕ запускаем polling на Render!
    # Вместо этого используем вебхуки
    
    if os.getenv('RENDER'):
        # На Render используем вебхуки
        logger.info("🌐 Настройка вебхуков для Render")
        
        # Удаляем существующие вебхуки
        bot.remove_webhook()
        time.sleep(1)
        
        # Получаем URL вашего сервиса на Render
        # Render автоматически устанавливает RENDER_EXTERNAL_URL
        render_url = os.getenv('RENDER_EXTERNAL_URL', '')
        if render_url:
            webhook_url = f"{render_url}/{BOT_TOKEN}"
            bot.set_webhook(url=webhook_url)
            logger.info(f"✅ Вебхук установлен: {webhook_url}")
        else:
            logger.error("❌ RENDER_EXTERNAL_URL не установлен!")
        
        # Запускаем Flask (он уже запущен в отдельном потоке)
        # Бот будет обрабатывать запросы через вебхуки
    else:
        # Локально используем polling
        logger.info("📱 Локальный запуск с polling")
        
        # Создаем начальное соединение
        try:
            get_db_connection()
            logger.info("✅ База данных подключена")
            
            bot_info = bot.get_me()
            logger.info(f"🤖 Бот: @{bot_info.username}")
            
            logger.info("✅ Бот готов к работе...")
            
            # Запускаем polling с обработкой ошибок
            while True:
                try:
                    bot.polling(none_stop=True, timeout=60)
                except Exception as e:
                    logger.error(f"❌ Ошибка polling: {e}")
                    time.sleep(15)
                    
        except KeyboardInterrupt:
            logger.info("⏹️ Остановка бота...")
            close_all_connections()