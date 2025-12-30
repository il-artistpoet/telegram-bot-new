# Работающий бот для Telegram с полным исправлением БД

import os
import telebot
import sqlite3
import threading
import atexit
from datetime import datetime, timedelta
import time
from flask import Flask, request
import logging

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

@app.route('/webhook', methods=['POST'])
def webhook():
    """Endpoint для получения обновлений от Telegram"""
    token = request.headers.get('X-Telegram-Bot-Token') or request.args.get('token')
    
    if token != BOT_TOKEN:
        return 'Unauthorized', 401
    
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Bad Request', 400

# ========== НАСТРОЙКИ ==========
BOT_TOKEN = "8432420548:AAGX_EqsarA7q_Jx4iNL2zV8j3c_JWd_POU"
CHANNEL_ID = "-1003227241488"
ADMIN_ID = 644037215
TILDA_LINK = "https://pleinairclub.tilda.ws/"

# РЕКВИЗИТЫ
SBER_PHONE = "+79043323607"
SBER_CARD = "2202208262152375"
YOUR_NAME = "Илья Козлов"

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
        # Сначала убедимся что файл существует
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        if not os.path.exists(DB_PATH):
            logger.info(f"📁 Создаем новый файл базы: {DB_PATH}")
            # Просто создаем пустой файл
            open(DB_PATH, 'w').close()
        
        if not hasattr(thread_local, "conn") or thread_local.conn is None:
            logger.info("🔌 Создаем новое соединение с БД")
            thread_local.conn = sqlite3.connect(
                DB_PATH, 
                check_same_thread=False,
                timeout=10
            )
            thread_local.cursor = thread_local.conn.cursor()
            
            # Оптимизация
            thread_local.conn.execute("PRAGMA journal_mode=WAL")
            thread_local.conn.execute("PRAGMA synchronous=NORMAL")
            
            # Создаем таблицы
            create_tables()
        
        return thread_local.conn, thread_local.cursor
    except Exception as e:
        logger.error(f"❌ Ошибка подключения к БД: {e}")
        # Если что-то пошло не так, сбрасываем соединение
        if hasattr(thread_local, "conn"):
            try:
                thread_local.conn.close()
            except:
                pass
            thread_local.conn = None
            thread_local.cursor = None
        raise

def create_tables():
    """Создает таблицы с правильной структурой"""
    try:
        cursor = thread_local.cursor
        
        # Таблица пользователей
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
        
        thread_local.conn.commit()
        logger.info("✅ Таблицы созданы/проверены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания таблиц: {e}")

def check_database_structure():
    """Проверяет структуру базы (вызывается при старте)"""
    try:
        # Просто создаем соединение - таблицы создадутся автоматически
        conn, cursor = get_db_connection()
        logger.info("✅ База данных проверена")
    except Exception as e:
        logger.error(f"❌ Ошибка проверки БД: {e}")

# ========== КОМАНДА /START ==========
@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"🚀 Команда /start от {message.from_user.id}")
    
    # Приветственное сообщение
    bot.send_message(
        message.chat.id,
        "Приветствую Вас. Оставайтесь на волне созерцания и пленэра!"
    )
    
    # ФОТО - упрощенная версия (без ошибок)
    try:
        # Просто сообщение вместо фото (пока не починим)
        bot.send_message(
            message.chat.id,
            "🎨 Художник Илья Козлов приветствует вас в Пленэрном Клубе!"
        )
        logger.info(f"📸 Текстовое приветствие для {message.from_user.id}")
    except Exception as e:
        logger.error(f"⚠️ Ошибка при отправке приветствия: {e}")
    
    # Основное сообщение с кнопками
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

# ========== ВОССТАНОВЛЕНИЕ БАЗЫ ==========
@bot.message_handler(commands=['fix_db'])
def fix_database(message):
    """Восстановление базы данных"""
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        # Закрываем старые соединения
        if hasattr(thread_local, "conn"):
            try:
                thread_local.conn.close()
            except:
                pass
            thread_local.conn = None
            thread_local.cursor = None
        
        # Удаляем старую базу
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
            logger.info("🗑️ Удален старый файл БД")
        
        # Создаем новую
        conn, cursor = get_db_connection()
        
        # Проверяем
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        response = "✅ БАЗА ДАННЫХ ВОССТАНОВЛЕНА!\n\n"
        response += f"Файл: {DB_PATH}\n"
        response += f"Таблицы: {len(tables)}\n"
        
        for table in tables:
            response += f"• {table[0]}\n"
        
        bot.reply_to(message, response)
        logger.info("✅ База восстановлена")
        
    except Exception as e:
        logger.error(f"❌ Ошибка восстановления: {e}")
        bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['db_status'])
def db_status(message):
    """Статус базы данных"""
    if message.from_user.id != ADMIN_ID:
        return
    
    response = f"📊 СТАТУС БАЗЫ ДАННЫХ:\n\n"
    response += f"Путь: {DB_PATH}\n"
    response += f"Существует: {'✅ Да' if os.path.exists(DB_PATH) else '❌ Нет'}\n"
    
    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        response += f"Размер: {size} байт\n"
    
    # Пробуем подключиться
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        
        response += f"\nТаблицы: {len(tables)}\n"
        for table in tables:
            response += f"• {table[0]}\n"
        
        response += "\n✅ База работает нормально"
        
    except Exception as e:
        response += f"\n❌ Ошибка подключения: {e}"
    
    bot.reply_to(message, response)

# ========== ОСТАЛЬНЫЕ КОМАНДЫ (упрощенные) ==========
@bot.message_handler(commands=['ping'])
def ping_command(message):
    bot.send_message(message.chat.id, "🏓 Pong! Бот работает!")

@bot.message_handler(commands=['testdb'])
def test_database(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        conn, cursor = get_db_connection()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        response = "📋 ТАБЛИЦЫ В БАЗЕ:\n"
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
            count = cursor.fetchone()[0]
            response += f"• {table[0]}: {count} записей\n"
        
        bot.send_message(ADMIN_ID, response)
        logger.info("✅ Тест БД выполнен")
        
    except Exception as e:
        logger.error(f"❌ Ошибка теста БД: {e}")
        bot.send_message(ADMIN_ID, f"❌ Ошибка: {str(e)[:200]}")

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
    
    # Проверяем базу
    check_database_structure()
    
    # Настройка для Render
    is_render = os.getenv('RENDER', False)
    
    if is_render:
        logger.info("🚀 Запускаем на Render")
        
        # Настраиваем вебхук
        render_url = os.getenv('RENDER_EXTERNAL_URL', '')
        if render_url:
            logger.info(f"🌐 Render URL: {render_url}")
            try:
                bot.remove_webhook()
                time.sleep(1)
                webhook_url = f"{render_url}/webhook?token={BOT_TOKEN}"
                bot.set_webhook(url=webhook_url)
                logger.info(f"✅ Вебхук установлен: {webhook_url}")
            except Exception as e:
                logger.error(f"❌ Ошибка вебхука: {e}")
        else:
            logger.warning("⚠️ RENDER_EXTERNAL_URL не найден")
        
        # Запускаем Flask
        logger.info("🚀 Запускаем Flask сервер...")
        app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)
        
    else:
        logger.info("📱 Локальный запуск")
        
        try:
            # Удаляем вебхук
            bot.remove_webhook()
            time.sleep(1)
            
            # Проверяем базу
            get_db_connection()
            logger.info("✅ База данных подключена")
            
            # Информация о боте
            bot_info = bot.get_me()
            logger.info(f"🤖 Бот: @{bot_info.username}")
            
            logger.info("✅ Бот готов к работе...")
            
            # Запускаем polling
            bot.polling(none_stop=True, timeout=60)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Остановка бота...")
            close_all_connections()
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")
            close_all_connections()