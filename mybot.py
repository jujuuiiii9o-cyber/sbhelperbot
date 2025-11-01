import os
import time
import asyncio
import json
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

# Конфигурация
BOT_TOKEN = "8379179520:AAEtv98Du5kOERtzLAuljEJ70dz9BeTk8Gg"
ADMIN_ID = 5395109783
COOLDOWN_TIME = 300  # 5 минут в секундах

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Словари для хранения состояний
user_cooldowns = {}
user_states = {}
user_languages = {}
appeal_states = {}  # Храним состояния обжалований

# Пагинация для списка заблокированных
blocked_users_pages = {}

# Система блокировок
class AdvancedUserBlocker:
    def __init__(self, filename='blocked_users.json'):
        self.filename = filename
        self.blocked_users = self._load_blocked_users()
    
    def _load_blocked_users(self):
        """Загрузить заблокированных пользователей из файла"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем старый формат в новый
                    if isinstance(data, list):
                        return {str(user_id): {
                            "blocked_at": datetime.now().isoformat(),
                            "reason": "Причина не указана",
                            "blocked_by": "Система",
                            "username": "Неизвестно",
                            "first_name": "Неизвестно",
                            "last_name": "",
                            "appeal_status": "not_appealed"
                        } for user_id in data}
                    # Конвертируем ключи в строки
                    return {str(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            print(f"Ошибка загрузки blocked_users: {e}")
            return {}
    
    def _save_blocked_users(self):
        """Сохранить заблокированных пользователей в файл"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.blocked_users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения blocked_users: {e}")
    
    def block_user(self, user_id, reason="Не указана", blocked_by="Система", 
                   username="Неизвестно", first_name="Неизвестно", last_name=""):
        """Заблокировать пользователя с причиной и временем"""
        user_id_str = str(user_id)
        if user_id_str in self.blocked_users:
            return f"❌ Пользователь {user_id} уже заблокирован."
        
        self.blocked_users[user_id_str] = {
            "blocked_at": datetime.now().isoformat(),
            "reason": reason,
            "blocked_by": blocked_by,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "appeal_status": "not_appealed"
        }
        self._save_blocked_users()
        return f"✅ Пользователь {user_id} заблокирован.\nПричина: {reason}"
    
    def unblock_user(self, user_id, unblock_reason="Не указана"):
        """Разблокировать пользователя с причиной"""
        user_id_str = str(user_id)
        if user_id_str not in self.blocked_users:
            return f"❌ Пользователь {user_id} не заблокирован.", None
            
        user_data = self.blocked_users[user_id_str]
        del self.blocked_users[user_id_str]
        self._save_blocked_users()
        return f"✅ Пользователь {user_id} разблокирован.\nПричина разблокировки: {unblock_reason}", user_data
    
    def is_blocked(self, user_id):
        """Проверить заблокирован ли пользователь"""
        return str(user_id) in self.blocked_users
    
    def get_block_info(self, user_id):
        """Получить информацию о блокировке пользователя"""
        user_id_str = str(user_id)
        if user_id_str in self.blocked_users:
            return self.blocked_users[user_id_str]
        return None
    
    def get_blocked_list(self):
        """Получить список всех заблокированных пользователей"""
        return self.blocked_users
    
    def format_block_message(self, user_id, lang="ru"):
        """Форматировать сообщение о блокировке для пользователя с учетом языка"""
        block_info = self.get_block_info(user_id)
        if not block_info:
            return None
        
        blocked_at = datetime.fromisoformat(block_info['blocked_at'])
        formatted_time = blocked_at.strftime("%d.%m.%Y в %H:%M:%S")
        
        if lang == "en":
            message = (
                "❌ <b>You are blocked in this bot</b>\n\n"
                f"<b>Block reason:</b> {block_info['reason']}\n"
                f"<b>Block date and time:</b> {formatted_time}\n"
                f"<b>Blocked by:</b> {block_info['blocked_by']}\n\n"
            )
            
            if block_info['appeal_status'] == 'not_appealed':
                message += "If you think this is a mistake, you can appeal the block."
            elif block_info['appeal_status'] == 'pending':
                message += "✅ Your appeal is under consideration by the administrator."
            elif block_info['appeal_status'] == 'rejected':
                message += "❌ Your appeal has been rejected. Repeated appeal is not possible."
        else:
            message = (
                "❌ <b>Вы заблокированы в этом боте</b>\n\n"
                f"<b>Причина блокировки:</b> {block_info['reason']}\n"
                f"<b>Дата и время блокировки:</b> {formatted_time}\n"
                f"<b>Заблокировал:</b> {block_info['blocked_by']}\n\n"
            )
            
            if block_info['appeal_status'] == 'not_appealed':
                message += "Если вы считаете, что это ошибка, вы можете обжаловать блокировку."
            elif block_info['appeal_status'] == 'pending':
                message += "✅ Ваше обжалование находится на рассмотрении администратором."
            elif block_info['appeal_status'] == 'rejected':
                message += "❌ Ваше обжалование было отклонено. Повторное обжалование невозможно."
        
        return message
    
    def update_appeal_status(self, user_id, status):
        """Обновить статус обжалования"""
        user_id_str = str(user_id)
        if user_id_str in self.blocked_users:
            self.blocked_users[user_id_str]['appeal_status'] = status
            self._save_blocked_users()
            return True
        return False

# Система языков
class UserLanguageManager:
    def __init__(self, filename='user_languages.json'):
        self.filename = filename
        self.user_languages = self._load_user_languages()
    
    def _load_user_languages(self):
        """Загрузить языки пользователей из файла"""
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем ключи в строки
                    return {str(k): v for k, v in data.items()}
            return {}
        except Exception as e:
            print(f"Ошибка загрузки user_languages: {e}")
            return {}
    
    def _save_user_languages(self):
        """Сохранить языки пользователей в файл"""
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.user_languages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения user_languages: {e}")
    
    def get_user_language(self, user_id):
        """Получить язык пользователя"""
        return self.user_languages.get(str(user_id))
    
    def set_user_language(self, user_id, lang_code):
        """Установить язык пользователя"""
        self.user_languages[str(user_id)] = lang_code
        self._save_user_languages()
    
    def get_all_users(self):
        """Получить всех пользователей с выбранным языком"""
        return self.user_languages

# Инициализация блокировщика и менеджера языков
user_blocker = AdvancedUserBlocker()
language_manager = UserLanguageManager()

def get_user_language(user_id):
    """Получаем язык пользователя"""
    return language_manager.get_user_language(user_id)

# Тексты на разных языках
TEXTS = {
    "ru": {
        "welcome": "<b>👋 | Добро пожаловать!</b>\n\n✏️ | С помощью этого бота вы можете связаться со мной по любым вопросам, если у вас недостаточно звезд для отправки сообщения напрямую или у вас имеется спамблок.\n\n📃 | По правилам обращения и другим известным вопросам я сразу написал.",
        "blocked": "❌ <b>Вы заблокированы и не можете использовать этого бота.</b>\n\nЕсли вы считаете, что это ошибка, свяжитесь с администратором.",
        "rules": "<b>📄 | Правила обращений</b>\n\n❌ | Запрещается:\n๑ Спам, флуд обращениями\n๑ Нецензурный контент \n๑ Попытки рекламы и мошенничества\n\n📌 | Сообщения должны быть по делу, уважайте время собеседника\n\n🔒 | <b>Нарушители блокируются без предупреждения!</b>",
        "write_msg": "<b>💬 | Написать сообщение</b>\n\nВы можете отправить любое сообщение (текст, фото, GIF, документ или стикер), и оно будет немедленно доставлено администратору.\n\n🕑 | <b>Следующее сообщение можно будет отправить через 5 минут.</b>",
        "report_sb_confirm": "<b>📨 | Сообщить о наличии СпамБлока</b>\n\nВы действительно хотите сообщить о действующем спамблоке владельцу бота?",
        "report_sb_success": "<b>✅ | Ваше сообщение о СБ успешно доставлено администратору!</b>\n\n🕑 | <b>Следующая возможность сообщить о наличии СпамБлока будет доступна через 5 минут.</b>",
        "report_bug": "<b>⛓️‍💥 | Сообщить об ошибке или предложить улучшение</b>\n\nОпишите обнаруженную ошибку, баг или предложите свое улучшение в работе бота (можно приложить скриншоты).\n\n🕑 | <b>Следующее обращение можно будет отправить через 5 минут.</b>",
        "bio": "<b>👤 | My bio</b>\n\nЗдесь, Вы можете ознакомиться с каналом владельца бота",
        "choose_language": "<b>🇷🇺 | Выберите язык \n🇺🇸 | Choose language</b>",
        "cooldown_message": "🕑 | <b>Следующее сообщение можно отправить через {remaining} секунд.</b>",
        "cooldown_sb": "🕑 | <b>Следующее сообщение о СпамБлоке можно отправить через {remaining} секунд.</b>",
        "cooldown_bug": "🕑 | <b>Следующее сообщение об улучшении/ошибке можно будет отправить через {remaining} секунд.</b>",
        "unknown_command": "🤔 | Не понимаю вашу команду. Используйте кнопку 'Назад' для возврата в главное меню.",
        "message_sent": "✅ | Ваше сообщение успешно доставлено администратору!",
        "sticker_not_allowed": "❌ | Стикеры не принимаются для данного типа сообщений.",
        "error_sending": "❌ | Произошла ошибка при отправке сообщения. Попробуйте еще раз.",
        "unblocked": "✅ | <b>Вы были разблокированы!</b>\n\nПричина разблокировки: {reason}\n\nТеперь вы снова можете использовать бота.",
        "appeal_sent": "✅ | Ваше обжалование отправлено на рассмотрение администратору.",
        "appeal_already_sent": "🕑 | Ваше обжалование уже находится на рассмотрении.",
        "appeal_rejected": "❌ | Вы не можете подать обжалование, так как предыдущее было отклонено.",
        "appeal_waiting": "📝 | <b>Подача обжалования</b>\n\nНапишите текст обжалования или прикрепите документ/фото/GIF, объясняющий вашу позицию.\n\n❌ | <b>Стикеры не принимаются</b>\n\nВы можете отправить только одно обжалование.",
        "unblock_reason_waiting": "📝 | <b>Добавление причины разблокировки</b>\n\nНапишите причину разблокировки для пользователя.\n\nЭта причина будет отправлена пользователю в уведомлении о разблокировке.",
        "unblock_success": "✅ | Пользователь успешно разблокирован\n\nПользователь был уведомлен о разблокировке.",
        "buttons": {
            "rules": "📜 Правила обращений",
            "write_msg": "✉ Написать сообщение", 
            "report_sb": "🚨 Сообщить о СБ",
            "report_bug": "⛓️‍💥 Сообщить об ошибке/улучшении",
            "bio": "👤 My bio",
            "language": "🌐 Язык",
            "back": "⬅️ Назад",
            "yes": "✅ Да",
            "no": "❌ Нет",
            "channel": "📢 Перейти в канал",
            "appeal": "📝 Обжаловать блокировку"
        }
    },
    "en": {
        "welcome": "<b>👋 | Welcome!</b>\n\n✏️ | With this bot you can contact me on any issues if you don't have enough stars to send a message directly or if you have a spam block.\n\n📃 | I have already written about the rules of communication and other known issues.",
        "blocked": "❌ <b>You are blocked and cannot use this bot.</b>\n\nIf you think this is a mistake, contact the administrator.",
        "rules": "<b>📄 | Communication Rules</b>\n\n❌ | Prohibited:\n๑ Spam, flood of appeals\n๑ Inappropriate content\n๑ Attempts of advertising and fraud\n\n📌 | Messages should be to the point, respect the interlocutor's time\n\n🔒 | <b>Violators are blocked without warning!</b>",
        "write_msg": "<b>💬 | Write a message</b>\n\nYou can send any message (text, photo, GIF, document or sticker), and it will be immediately delivered to the administrator.\n\n🕑 | <b>Next message can be sent in 5 minutes.</b>",
        "report_sb_confirm": "<b>📨 | Report Spam Block</b>\n\nDo you really want to report an active spam block to the bot owner?",
        "report_sb_success": "<b>✅ | Your spam block report has been successfully delivered to the administrator!</b>\n\n🕑 | <b>Next opportunity to report a spam block will be available in 5 minutes.</b>",
        "report_bug": "<b>⛓️‍💥 | Report an error or suggest improvement</b>\n\nDescribe the detected error, bug or suggest your improvement in the bot's operation (you can attach screenshots).\n\n🕑 | <b>Next appeal can be sent in 5 minutes.</b>",
        "bio": "<b>👤 | My bio</b>\n\nHere you can check out the bot owner's channel",
        "choose_language": "<b>🇷🇺 | Выберите язык \n🇺🇸 | Choose language</b>",
        "cooldown_message": "🕑 | <b>Next message can be sent in {remaining} seconds.</b>",
        "cooldown_sb": "🕑 | <b>Next spam block report can be sent in {remaining} seconds.</b>",
        "cooldown_bug": "🕑 | <b>Next improvement/error report can be sent in {remaining} seconds.</b>",
        "unknown_command": "🤔 | I don't understand your command. Use the 'Back' button to return to the main menu.",
        "message_sent": "✅ | Your message has been successfully delivered to the administrator!",
        "sticker_not_allowed": "❌ | Stickers are not accepted for this message type.",
        "error_sending": "❌ | An error occurred while sending the message. Please try again.",
        "unblocked": "✅ | <b>You have been unblocked!</b>\n\nUnblock reason: {reason}\n\nYou can now use the bot again.",
        "appeal_sent": "✅ | Your appeal has been sent to the administrator for review.",
        "appeal_already_sent": "🕑 | Your appeal is already under review.",
        "appeal_rejected": "❌ | You cannot file an appeal because the previous one was rejected.",
        "appeal_waiting": "📝 | <b>Appeal Submission</b>\n\nWrite your appeal text or attach a document/photo/GIF explaining your position.\n\n❌ | <b>Stickers are not accepted</b>\n\nYou can only submit one appeal.",
        "unblock_reason_waiting": "📝 | <b>Adding Unblock Reason</b>\n\nWrite the reason for unblocking the user.\n\nThis reason will be sent to the user in the unblock notification.",
        "unblock_success": "✅ | User successfully unblocked\n\nThe user has been notified of the unblock.",
        "buttons": {
            "rules": "📜 Communication Rules",
            "write_msg": "✉ Write Message", 
            "report_sb": "🚨 Report Spam Block",
            "report_bug": "⛓️‍💥 Report Error/Improvement",
            "bio": "👤 My Bio",
            "language": "🌐 Language",
            "back": "⬅️ Back",
            "yes": "✅ Yes",
            "no": "❌ No",
            "channel": "📢 Go to Channel",
            "appeal": "📝 Appeal Block"
        }
    }
}

def main_keyboard(user_id):
    """Клавиатура для главного меню"""
    lang = get_user_language(user_id)
    if not lang:
        return None
    
    texts = TEXTS[lang]["buttons"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=texts["rules"], callback_data="rules"))
    keyboard.row(InlineKeyboardButton(text=texts["write_msg"], callback_data="write_msg"))
    keyboard.row(InlineKeyboardButton(text=texts["report_sb"], callback_data="report_sb"))
    keyboard.row(InlineKeyboardButton(text=texts["report_bug"], callback_data="report_bug"))
    keyboard.row(
        InlineKeyboardButton(text=texts["bio"], callback_data="bio"),
        InlineKeyboardButton(text=texts["language"], callback_data="language")
    )
    
    # Убрана кнопка админ-панели
    return keyboard.as_markup()

def back_keyboard(user_id):
    """Клавиатура с одной кнопкой 'Назад'"""
    lang = get_user_language(user_id)
    if not lang:
        return None
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=TEXTS[lang]["buttons"]["back"], callback_data="back_to_main"))
    return keyboard.as_markup()

def blocked_user_keyboard(user_id):
    """Клавиатура для заблокированного пользователя"""
    lang = get_user_language(user_id) or "ru"
    texts = TEXTS[lang]["buttons"]
    
    keyboard = InlineKeyboardBuilder()
    
    block_info = user_blocker.get_block_info(user_id)
    if block_info and block_info.get('appeal_status') == 'not_appealed':
        keyboard.row(InlineKeyboardButton(text=texts["appeal"], callback_data=f"appeal_block_{user_id}"))
    
    keyboard.row(InlineKeyboardButton(text=texts["language"], callback_data="language"))
    
    return keyboard.as_markup()

def appeal_back_keyboard(user_id):
    """Клавиатура для возврата из обжалования к сообщению о блокировке"""
    lang = get_user_language(user_id) or "ru"
    texts = TEXTS[lang]["buttons"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=texts["back"], callback_data="back_to_blocked"))
    return keyboard.as_markup()

def confirm_sb_keyboard(user_id):
    """Клавиатура для подтверждения сообщения о СБ"""
    lang = get_user_language(user_id)
    if not lang:
        return None
    
    texts = TEXTS[lang]["buttons"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(text=texts["yes"], callback_data="confirm_sb_yes"),
        InlineKeyboardButton(text=texts["no"], callback_data="confirm_sb_no")
    )
    keyboard.row(InlineKeyboardButton(text=texts["back"], callback_data="back_to_main"))
    return keyboard.as_markup()

def bio_keyboard(user_id):
    """Клавиатура для раздела My bio"""
    lang = get_user_language(user_id)
    if not lang:
        return None
    
    texts = TEXTS[lang]["buttons"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text=texts["channel"], url="https://t.me/hatetearz"))
    keyboard.row(InlineKeyboardButton(text=texts["back"], callback_data="back_to_main"))
    return keyboard.as_markup()

def language_keyboard():
    """Клавиатура для выбора языка (без кнопки Назад для первого выбора)"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"))
    keyboard.row(InlineKeyboardButton(text="🇺🇸 English", callback_data="set_lang_en"))
    
    return keyboard.as_markup()

def language_keyboard_with_back(user_id):
    """Клавиатура для выбора языка с кнопкой Назад"""
    current_lang = get_user_language(user_id)
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(InlineKeyboardButton(
        text=f"🇷🇺 Русский {'✅' if current_lang == 'ru' else ''}", 
        callback_data="set_lang_ru"
    ))
    keyboard.row(InlineKeyboardButton(
        text=f"🇺🇸 English {'✅' if current_lang == 'en' else ''}", 
        callback_data="set_lang_en"
    ))
    keyboard.row(InlineKeyboardButton(
        text=TEXTS[get_user_language(user_id) or "ru"]["buttons"]["back"], 
        callback_data="back_to_main"
    ))
    
    return keyboard.as_markup()

def admin_panel_keyboard():
    """Клавиатура админ-панели"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(InlineKeyboardButton(text="📋 Список заблокированных", callback_data="admin_blocked_list"))
    keyboard.row(InlineKeyboardButton(text="🚫 Заблокировать пользователя", callback_data="admin_block_user"))
    keyboard.row(InlineKeyboardButton(text="✅ Разблокировать пользователя", callback_data="admin_unblock_user"))
    keyboard.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    keyboard.row(InlineKeyboardButton(text="📨 Активные обжалования", callback_data="admin_appeals"))
    # Убрана кнопка "Главное меню"
    
    return keyboard.as_markup()

def appeal_decision_keyboard(user_id):
    """Клавиатура для решения по обжалованию"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(
        InlineKeyboardButton(text="✅ Принять обжалование", callback_data=f"appeal_approve_{user_id}"),
        InlineKeyboardButton(text="❌ Отклонить обжалование", callback_data=f"appeal_reject_{user_id}")
    )
    
    return keyboard.as_markup()

def get_blocked_users_page_keyboard(page=1, page_size=6):
    """Клавиатура для пагинации списка заблокированных пользователей"""
    blocked_users = user_blocker.get_blocked_list()
    user_ids = list(blocked_users.keys())
    
    total_pages = (len(user_ids) + page_size - 1) // page_size
    
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_users = user_ids[start_idx:end_idx]
    
    keyboard = InlineKeyboardBuilder()
    
    # Добавляем кнопки пользователей (максимум 6)
    for user_id in page_users:
        user_info = blocked_users[user_id]
        username = user_info.get('username', 'Неизвестно')
        button_text = f"👤 {user_id} ({username})"
        if len(button_text) > 30:
            button_text = button_text[:27] + "..."
        keyboard.row(InlineKeyboardButton(
            text=button_text,
            callback_data=f"admin_user_info_{user_id}_{page}"
        ))
    
    # Добавляем пагинацию
    pagination_row = []
    if page > 1:
        pagination_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_blocked_page_{page-1}"))
    
    pagination_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="current_page"))
    
    if page < total_pages:
        pagination_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_blocked_page_{page+1}"))
    
    if pagination_row:
        keyboard.row(*pagination_row)
    
    # Кнопка назад
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_panel"))
    
    return keyboard.as_markup(), page, total_pages

def get_user_info_keyboard(user_id, from_page):
    """Клавиатура для информации о конкретном пользователе"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(InlineKeyboardButton(text="✅ Разблокировать", callback_data=f"admin_unblock_confirm_{user_id}_{from_page}"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад к списку", callback_data=f"admin_blocked_page_{from_page}"))
    
    return keyboard.as_markup()

def get_unblock_confirmation_keyboard(user_id, from_page):
    """Клавиатура для подтверждения разблокировки"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"admin_unblock_yes_{user_id}_{from_page}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"admin_unblock_no_{user_id}_{from_page}")
    )
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_user_info_{user_id}_{from_page}"))
    
    return keyboard.as_markup()

def get_unblock_reason_keyboard(user_id, from_page):
    """Клавиатура для выбора причины разблокировки"""
    keyboard = InlineKeyboardBuilder()
    
    keyboard.row(InlineKeyboardButton(text="📝 Добавить причину", callback_data=f"admin_unblock_with_reason_{user_id}_{from_page}"))
    keyboard.row(InlineKeyboardButton(text="⏩ Пропустить причину", callback_data=f"admin_unblock_skip_reason_{user_id}_{from_page}"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_unblock_confirm_{user_id}_{from_page}"))
    
    return keyboard.as_markup()

def get_unblock_success_keyboard():
    """Клавиатура после успешной разблокировки"""
    # Возвращаем пустую клавиатуру (без кнопок)
    return InlineKeyboardBuilder().as_markup()

async def safe_edit_message_text(chat_id, message_id, text, reply_markup=None, parse_mode=ParseMode.HTML):
    """Безопасное редактирование текстового сообщения"""
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "message to edit not found" in str(e):
            # Если сообщение не найдено, отправляем новое
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            print(f"Ошибка редактирования сообщения: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )

async def safe_edit_message_caption(chat_id, message_id, caption, reply_markup=None, parse_mode=ParseMode.HTML):
    """Безопасное редактирование подписи сообщения с медиа"""
    try:
        await bot.edit_message_caption(
            chat_id=chat_id,
            message_id=message_id,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        elif "message to edit not found" in str(e) or "no caption in the message to edit" in str(e):
            # Если сообщение не найдено или нет подписи, отправляем новое текстовое сообщение
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            print(f"Ошибка редактирования подписи: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

async def send_language_selection(chat_id, message_id=None):
    """Функция для отправки выбора языка с картинкой"""
    try:
        if os.path.exists('welcome.jpg'):
            if message_id:
                # Редактируем существующее сообщение
                await safe_edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=TEXTS["ru"]["choose_language"],
                    reply_markup=language_keyboard()
                )
            else:
                # Отправляем новое сообщение с фото
                with open('welcome.jpg', 'rb') as photo:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=types.BufferedInputFile(photo.read(), filename="welcome.jpg"),
                        caption=TEXTS["ru"]["choose_language"],
                        reply_markup=language_keyboard(),
                        parse_mode=ParseMode.HTML
                    )
        else:
            if message_id:
                await safe_edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=TEXTS["ru"]["choose_language"],
                    reply_markup=language_keyboard(),
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=TEXTS["ru"]["choose_language"],
                    reply_markup=language_keyboard(),
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        print(f"Ошибка при отправке выбора языка: {e}")

async def send_main_menu(chat_id, user_id, message_id=None):
    """Функция для отправки главного меню с картинкой"""
    lang = get_user_language(user_id)
    if not lang:
        await send_language_selection(chat_id, message_id)
        return
    
    try:
        if os.path.exists('welcome.jpg'):
            if message_id:
                # Редактируем существующее сообщение
                await safe_edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=TEXTS[lang]["welcome"],
                    reply_markup=main_keyboard(user_id)
                )
            else:
                # Отправляем новое сообщение с фото
                with open('welcome.jpg', 'rb') as photo:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=types.BufferedInputFile(photo.read(), filename="welcome.jpg"),
                        caption=TEXTS[lang]["welcome"],
                        reply_markup=main_keyboard(user_id),
                        parse_mode=ParseMode.HTML
                    )
        else:
            if message_id:
                await safe_edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=TEXTS[lang]["welcome"],
                    reply_markup=main_keyboard(user_id),
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=TEXTS[lang]["welcome"],
                    reply_markup=main_keyboard(user_id),
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        print(f"Ошибка при отправке главного меню: {e}")
        # Fallback: отправляем текстовое сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=TEXTS[lang]["welcome"],
            reply_markup=main_keyboard(user_id),
            parse_mode=ParseMode.HTML
        )

async def send_admin_panel(chat_id, message_id=None):
    """Функция для отправки админ-панели с картинкой"""
    try:
        if os.path.exists('admin_panel.jpg'):
            if message_id:
                # Редактируем существующее сообщение
                await safe_edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption="🛠️ <b>Панель администратора</b>\n\nВыберите действие:",
                    reply_markup=admin_panel_keyboard()
                )
            else:
                # Отправляем новое сообщение с фото
                with open('admin_panel.jpg', 'rb') as photo:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=types.BufferedInputFile(photo.read(), filename="admin_panel.jpg"),
                        caption="🛠️ <b>Панель администратора</b>\n\nВыберите действие:",
                        reply_markup=admin_panel_keyboard(),
                        parse_mode=ParseMode.HTML
                    )
        else:
            if message_id:
                await safe_edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text="🛠️ <b>Панель администратора</b>\n\nВыберите действие:",
                    reply_markup=admin_panel_keyboard(),
                    parse_mode=ParseMode.HTML
                )
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="🛠️ <b>Панель администратора</b>\n\nВыберите действие:",
                    reply_markup=admin_panel_keyboard(),
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        print(f"Ошибка при отправке админ-панели: {e}")
        # Fallback: отправляем текстовое сообщение
        await bot.send_message(
            chat_id=chat_id,
            text="🛠️ <b>Панель администратора</b>\n\nВыберите действие:",
            reply_markup=admin_panel_keyboard(),
            parse_mode=ParseMode.HTML
        )

def check_cooldown(user_id, action, current_time):
    key = f"{user_id}_{action}"
    if key in user_cooldowns:
        if current_time - user_cooldowns[key] < COOLDOWN_TIME:
            return False
    return True

def get_remaining_cooldown(user_id, action, current_time):
    key = f"{user_id}_{action}"
    if key in user_cooldowns:
        remaining = COOLDOWN_TIME - (current_time - user_cooldowns[key])
        return max(0, int(remaining))
    return 0

# Мидлварь для проверки блокировки (только для сообщений, не для callback)
@dp.message.middleware()
async def block_check_middleware(handler, event, data):
    user_id = event.from_user.id
    
    if user_blocker.is_blocked(user_id):
        # Если пользователь в состоянии обжалования, пропускаем
        if user_states.get(user_id, {}).get('waiting_for_appeal'):
            return await handler(event, data)
            
        # Получаем детализированное сообщение о блокировке с учетом языка
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        
        # Добавляем кнопку обжалования если это возможно
        keyboard = blocked_user_keyboard(user_id)
        
        await event.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    return await handler(event, data)

# Основные обработчики бота
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        await message.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    # Если пользователь уже выбирал язык, сразу показываем главное меню
    if get_user_language(user_id):
        await send_main_menu(message.chat.id, user_id)
    else:
        # Иначе предлагаем выбрать язык
        await send_language_selection(message.chat.id)

@dp.callback_query(F.data == "back_to_main")
async def back_to_main_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=block_message,
                reply_markup=keyboard
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=block_message,
                reply_markup=keyboard
            )
        return
    
    if user_id in user_states:
        user_states[user_id] = {}
    
    # Всегда редактируем текущее сообщение
    await send_main_menu(callback.message.chat.id, user_id, callback.message.message_id)

@dp.callback_query(F.data == "rules")
async def rules_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=TEXTS[lang]["rules"],
            reply_markup=back_keyboard(user_id)
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=TEXTS[lang]["rules"],
            reply_markup=back_keyboard(user_id)
        )

@dp.callback_query(F.data == "write_msg")
async def write_msg_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    current_time = time.time()
    
    if check_cooldown(user_id, "write_msg", current_time):
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["write_msg"],
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["write_msg"],
                reply_markup=back_keyboard(user_id)
            )
        user_states[user_id] = {"waiting_for_message": True, "message_type": "regular"}
    else:
        remaining = get_remaining_cooldown(user_id, "write_msg", current_time)
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["cooldown_message"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["cooldown_message"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )

@dp.callback_query(F.data == "report_sb")
async def report_sb_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    current_time = time.time()
    
    if not check_cooldown(user_id, "report_sb", current_time):
        remaining = get_remaining_cooldown(user_id, "report_sb", current_time)
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["cooldown_sb"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["cooldown_sb"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )
    else:
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["report_sb_confirm"],
                reply_markup=confirm_sb_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["report_sb_confirm"],
                reply_markup=confirm_sb_keyboard(user_id)
            )

@dp.callback_query(F.data == "confirm_sb_yes")
async def confirm_sb_yes_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    current_time = time.time()
    
    if check_cooldown(user_id, "report_sb", current_time):
        user = callback.from_user
        admin_text = (
            f"🚨 СООБЩЕНИЕ О СБ\n"
            f"👤 Имя: {user.first_name}\n"
            f"👤 Фамилия: {user.last_name if user.last_name else 'Не указана'}\n"
            f"🔗 Юзернейм: @{user.username if user.username else 'отсутствует'}\n"
            f"🆔 ID: {user.id}\n"
            f"📅 Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            "────────────────────"
        )
        
        await bot.send_message(ADMIN_ID, admin_text)
        user_cooldowns[f"{user_id}_report_sb"] = current_time
        
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["report_sb_success"],
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["report_sb_success"],
                reply_markup=back_keyboard(user_id)
            )
    else:
        remaining = get_remaining_cooldown(user_id, "report_sb", current_time)
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["cooldown_sb"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["cooldown_sb"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )

@dp.callback_query(F.data == "confirm_sb_no")
async def confirm_sb_no_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await send_main_menu(callback.message.chat.id, user_id, callback.message.message_id)

@dp.callback_query(F.data == "report_bug")
async def report_bug_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    current_time = time.time()
    
    if check_cooldown(user_id, "report_bug", current_time):
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["report_bug"],
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["report_bug"],
                reply_markup=back_keyboard(user_id)
            )
        user_states[user_id] = {"waiting_for_message": True, "message_type": "bug"}
    else:
        remaining = get_remaining_cooldown(user_id, "report_bug", current_time)
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=TEXTS[lang]["cooldown_bug"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=TEXTS[lang]["cooldown_bug"].format(remaining=remaining),
                reply_markup=back_keyboard(user_id)
            )

@dp.callback_query(F.data == "bio")
async def bio_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang = get_user_language(user_id)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=TEXTS[lang]["bio"],
            reply_markup=bio_keyboard(user_id)
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=TEXTS[lang]["bio"],
            reply_markup=bio_keyboard(user_id)
        )

@dp.callback_query(F.data == "language")
async def language_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=TEXTS["ru"]["choose_language"],
            reply_markup=language_keyboard_with_back(user_id)
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=TEXTS["ru"]["choose_language"],
            reply_markup=language_keyboard_with_back(user_id)
        )

@dp.callback_query(F.data.startswith("set_lang_"))
async def set_language_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    lang_code = callback.data.split("_")[2]  # set_lang_ru -> ru
    
    # Сохраняем язык пользователя
    language_manager.set_user_language(user_id, lang_code)
    
    # Если пользователь заблокирован, показываем сообщение о блокировке на новом языке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        
        if callback.message.photo:
            await safe_edit_message_caption(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                caption=block_message,
                reply_markup=keyboard
            )
        else:
            await safe_edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=block_message,
                reply_markup=keyboard
            )
    else:
        # После смены языка возвращаем в главное меню
        await send_main_menu(callback.message.chat.id, user_id, callback.message.message_id)

# Команды администратора
@dp.message(Command("admin"))
async def admin_panel_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    await send_admin_panel(message.chat.id)

@dp.message(Command("block"))
async def block_user_handler(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    if not command.args:
        await message.answer("❌ Использование: /block <user_id> [причина]")
        return
    
    try:
        args = command.args.split(' ', 1)
        user_id = int(args[0])
        reason = args[1] if len(args) > 1 else "Не указана"
        
        # Проверяем, не заблокирован ли пользователь уже
        if user_blocker.is_blocked(user_id):
            await message.answer(f"❌ Пользователь {user_id} уже заблокирован.")
            return
        
        # Получаем информацию о пользователе
        username = "Неизвестно"
        first_name = "Неизвестно"
        last_name = ""
        try:
            user = await bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else user.first_name
            first_name = user.first_name or "Неизвестно"
            last_name = user.last_name or ""
        except:
            pass
        
        # Форматируем информацию о том, кто заблокировал
        admin_info = f"Администратор @{message.from_user.username} (ID: {message.from_user.id})" if message.from_user.username else f"Администратор (ID: {message.from_user.id})"
        
        result = user_blocker.block_user(user_id, reason, admin_info, username, first_name, last_name)
        await message.answer(result)
        
        # Пытаемся уведомить пользователя
        try:
            lang = get_user_language(user_id) or "ru"
            block_message = user_blocker.format_block_message(user_id, lang)
            keyboard = blocked_user_keyboard(user_id)
            await bot.send_message(user_id, block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception as e:
            await message.answer(f"✅ Пользователь заблокирован, но уведомление не отправлено: {e}")
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")

@dp.message(Command("unblock"))
async def unblock_user_handler(message: types.Message, command: CommandObject):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    if not command.args:
        await message.answer("❌ Использование: /unblock <user_id> [причина_разблокировки]")
        return
    
    try:
        args = command.args.split(' ', 1)
        user_id = int(args[0])
        unblock_reason = args[1] if len(args) > 1 else "Решение администратора"
        
        result, user_data = user_blocker.unblock_user(user_id, unblock_reason)
        await message.answer(result)
        
        # Пытаемся уведомить пользователя
        if user_data:
            try:
                lang = get_user_language(user_id) or "ru"
                await bot.send_message(
                    user_id, 
                    TEXTS[lang]["unblocked"].format(reason=unblock_reason), 
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                await message.answer(f"✅ Пользователь разблокирован, но уведомление не отправлено: {e}")
            
    except ValueError:
        await message.answer("❌ Неверный ID пользователя")

@dp.message(Command("blocked"))
async def list_blocked_users_handler(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ У вас нет прав для использования этой команды.")
        return
    
    blocked_users = user_blocker.get_blocked_list()
    
    if not blocked_users:
        await message.answer("📝 Список заблокированных пользователей пуст.")
        return
    
    blocked_list = []
    for user_id, info in blocked_users.items():
        blocked_at = datetime.fromisoformat(info['blocked_at'])
        formatted_time = blocked_at.strftime("%d.%m.%Y | %H:%M:%S")
        blocked_list.append(
            f"• <code>{user_id}</code> (@{info['username']}) - {formatted_time}\n"
            f"  Причина: {info['reason']}\n"
            f"  Заблокировал: {info['blocked_by']}\n"
            f"  Статус обжалования: {info.get('appeal_status', 'not_appealed')}"
        )
    
    response = "📝 <b>Заблокированные пользователи:</b>\n\n" + "\n\n".join(blocked_list)
    await message.answer(response, parse_mode=ParseMode.HTML)

# Обработчики админ-панели
@dp.callback_query(F.data == "admin_panel")
async def admin_panel_callback_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    await send_admin_panel(callback.message.chat.id, callback.message.message_id)

@dp.callback_query(F.data == "admin_blocked_list")
async def admin_blocked_list_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    blocked_users = user_blocker.get_blocked_list()
    
    if not blocked_users:
        await callback.answer("📝 Список заблокированных пользователей пуст.", show_alert=True)
        return
    
    # Показываем первую страницу списка заблокированных
    keyboard, current_page, total_pages = get_blocked_users_page_keyboard(1)
    text = f"📝 <b>Заблокированные пользователи</b>\n\nСтраница {current_page} из {total_pages}\nВыберите пользователя для просмотра информации:"
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("admin_blocked_page_"))
async def admin_blocked_page_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    page = int(callback.data.split("_")[3])
    keyboard, current_page, total_pages = get_blocked_users_page_keyboard(page)
    text = f"📝 <b>Заблокированные пользователи</b>\n\nСтраница {current_page} из {total_pages}\nВыберите пользователя для просмотра информации:"
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("admin_user_info_"))
async def admin_user_info_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[3]
    from_page = int(parts[4])
    
    block_info = user_blocker.get_block_info(user_id)
    if not block_info:
        await callback.answer("❌ Пользователь не найден в списке блокировок.", show_alert=True)
        return
    
    blocked_at = datetime.fromisoformat(block_info['blocked_at'])
    formatted_time = blocked_at.strftime("%d.%m.%Y в %H:%M:%S")
    
    text = (
        f"🔒 <b>Информация о блокировке</b>\n\n"
        f"<b>ID пользователя:</b> <code>{user_id}</code>\n"
        f"<b>Имя:</b> {block_info['first_name']}\n"
        f"<b>Фамилия:</b> {block_info.get('last_name', 'Не указана')}\n"
        f"<b>Username:</b> @{block_info['username']}\n"
        f"<b>Дата и время блокировки:</b> {formatted_time}\n"
        f"<b>Причина блокировки:</b> {block_info['reason']}\n"
        f"<b>Заблокировал:</b> {block_info['blocked_by']}\n"
        f"<b>Статус обжалования:</b> {block_info.get('appeal_status', 'not_appealed')}"
    )
    
    keyboard = get_user_info_keyboard(user_id, from_page)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("admin_unblock_confirm_"))
async def admin_unblock_confirm_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[3]
    from_page = int(parts[4])
    
    text = (
        f"🔓 <b>Подтверждение разблокировки</b>\n\n"
        f"Вы действительно хотите разблокировать пользователя <code>{user_id}</code>?\n\n"
        f"После разблокировки пользователь сможет снова использовать бота."
    )
    
    keyboard = get_unblock_confirmation_keyboard(user_id, from_page)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("admin_unblock_yes_"))
async def admin_unblock_yes_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[3]
    from_page = int(parts[4])
    
    text = (
        f"🔓 <b>Выбор причины разблокировки</b>\n\n"
        f"Выберите, хотите ли вы добавить причину разблокировки для пользователя <code>{user_id}</code>."
    )
    
    keyboard = get_unblock_reason_keyboard(user_id, from_page)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data.startswith("admin_unblock_with_reason_"))
async def admin_unblock_with_reason_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[4]
    from_page = int(parts[5])
    
    # Сохраняем состояние ожидания причины
    user_states[ADMIN_ID] = {
        "waiting_for_unblock_reason": True,
        "unblock_user_id": user_id,
        "unblock_from_page": from_page
    }
    
    text = TEXTS["ru"]["unblock_reason_waiting"]
    
    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"admin_unblock_yes_{user_id}_{from_page}"))
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard.as_markup()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard.as_markup()
        )

@dp.callback_query(F.data.startswith("admin_unblock_skip_reason_"))
async def admin_unblock_skip_reason_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[4]
    from_page = int(parts[5])
    
    # Разблокируем пользователя без причины
    result, user_data = user_blocker.unblock_user(user_id, "Решение администратора")
    
    # Очищаем состояние
    user_states[ADMIN_ID] = {}
    
    # Показываем сообщение об успешной разблокировке без кнопки "Назад"
    text = TEXTS["ru"]["unblock_success"]
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=None  # Убрана клавиатура
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=None  # Убрана клавиатура
        )
    
    # Уведомляем пользователя
    if user_data:
        try:
            lang = get_user_language(int(user_id)) or "ru"
            await bot.send_message(
                int(user_id), 
                TEXTS[lang]["unblocked"].format(reason="Решение администратора"), 
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Не удалось уведомить пользователя {user_id}: {e}")

@dp.callback_query(F.data.startswith("admin_unblock_no_"))
async def admin_unblock_no_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    parts = callback.data.split("_")
    user_id = parts[3]
    from_page = int(parts[4])
    
    # Возвращаем к информации о пользователе
    block_info = user_blocker.get_block_info(user_id)
    if not block_info:
        await callback.answer("❌ Пользователь не найден в списке блокировок.", show_alert=True)
        return
    
    blocked_at = datetime.fromisoformat(block_info['blocked_at'])
    formatted_time = blocked_at.strftime("%d.%m.%Y в %H:%M:%S")
    
    text = (
        f"🔒 <b>Информация о блокировке</b>\n\n"
        f"<b>ID пользователя:</b> <code>{user_id}</code>\n"
        f"<b>Имя:</b> {block_info['first_name']}\n"
        f"<b>Фамилия:</b> {block_info.get('last_name', 'Не указана')}\n"
        f"<b>Username:</b> @{block_info['username']}\n"
        f"<b>Дата и время блокировки:</b> {formatted_time}\n"
        f"<b>Причина блокировки:</b> {block_info['reason']}\n"
        f"<b>Заблокировал:</b> {block_info['blocked_by']}\n"
        f"<b>Статус обжалования:</b> {block_info.get('appeal_status', 'not_appealed')}"
    )
    
    keyboard = get_user_info_keyboard(user_id, from_page)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=keyboard
        )

@dp.callback_query(F.data == "back_to_admin")
async def back_to_admin_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    await send_admin_panel(callback.message.chat.id, callback.message.message_id)

@dp.callback_query(F.data == "admin_block_user")
async def admin_block_user_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    text = (
        "🚫 <b>Заблокировать пользователя</b>\n\n"
        "Для блокировки пользователя используйте команду:\n"
        "<code>/block ID_пользователя причина</code>\n\n"
        "Пример:\n"
        "<code>/block 123456789 Нарушение правил</code>"
    )
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=admin_panel_keyboard()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=admin_panel_keyboard()
        )

@dp.callback_query(F.data == "admin_unblock_user")
async def admin_unblock_user_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    text = (
        "✅ <b>Разблокировать пользователя</b>\n\n"
        "Для разблокировки пользователя используйте команду:\n"
        "<code>/unblock ID_пользователя [причина_разблокировки]</code>\n\n"
        "Пример:\n"
        "<code>/unblock 123456789 Ошибка модерации</code>"
    )
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=admin_panel_keyboard()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=admin_panel_keyboard()
        )

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    blocked_count = len(user_blocker.get_blocked_list())
    users_with_lang = len(language_manager.get_all_users())
    
    # Подсчет обжалований
    appeals_count = 0
    blocked_users = user_blocker.get_blocked_list()
    for user_id, info in blocked_users.items():
        if info.get('appeal_status') == 'pending':
            appeals_count += 1
    
    stats_text = (
        "📊 <b>Статистика бота</b>\n\n"
        f"<b>Заблокированных пользователей:</b> {blocked_count}\n"
        f"<b>Активных обжалований:</b> {appeals_count}\n"
        f"<b>Пользователей с выбором языка:</b> {users_with_lang}\n"
        f"<b>Всего уникальных пользователей:</b> {users_with_lang + blocked_count}"
    )
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=stats_text,
            reply_markup=admin_panel_keyboard()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=stats_text,
            reply_markup=admin_panel_keyboard()
        )

@dp.callback_query(F.data == "admin_appeals")
async def admin_appeals_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    blocked_users = user_blocker.get_blocked_list()
    appeals_list = []
    
    for user_id, info in blocked_users.items():
        if info.get('appeal_status') == 'pending':
            blocked_at = datetime.fromisoformat(info['blocked_at'])
            formatted_time = blocked_at.strftime("%d.%m.%Y | %H:%M:%S")
            appeals_list.append(
                f"• <code>{user_id}</code> (@{info['username']}) - {formatted_time}\n"
                f"  Причина блокировки: {info['reason']}\n"
                f"  <i>Ожидает рассмотрения</i>"
            )
    
    if not appeals_list:
        await callback.answer("📨 Активные обжалования отсутствуют.", show_alert=True)
        return
    
    text = "📨 <b>Активные обжалования:</b>\n\n" + "\n\n".join(appeals_list)
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=admin_panel_keyboard()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=admin_panel_keyboard()
        )

# Обработчики обжалований
@dp.callback_query(F.data.startswith("appeal_block_"))
async def appeal_block_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    target_user_id = int(callback.data.split("_")[2])
    
    # Проверяем, что пользователь обжалует свою собственную блокировку
    if user_id != target_user_id:
        await callback.answer("❌ Вы можете обжаловать только свою блокировку.", show_alert=True)
        return
    
    block_info = user_blocker.get_block_info(user_id)
    if not block_info:
        await callback.answer("❌ Вы не заблокированы.", show_alert=True)
        return
    
    if block_info.get('appeal_status') == 'pending':
        await callback.answer(TEXTS[get_user_language(user_id) or "ru"]["appeal_already_sent"], show_alert=True)
        return
    
    if block_info.get('appeal_status') == 'rejected':
        await callback.answer(TEXTS[get_user_language(user_id) or "ru"]["appeal_rejected"], show_alert=True)
        return
    
    # Устанавливаем состояние ожидания обжалования
    user_states[user_id] = {"waiting_for_appeal": True}
    
    lang = get_user_language(user_id) or "ru"
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=TEXTS[lang]["appeal_waiting"],
            reply_markup=appeal_back_keyboard(user_id)
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=TEXTS[lang]["appeal_waiting"],
            reply_markup=appeal_back_keyboard(user_id)
        )

@dp.callback_query(F.data == "back_to_blocked")
async def back_to_blocked_handler(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    # Сбрасываем состояние обжалования
    if user_id in user_states:
        user_states[user_id] = {}
    
    # Показываем сообщение о блокировке
    lang = get_user_language(user_id) or "ru"
    block_message = user_blocker.format_block_message(user_id, lang)
    keyboard = blocked_user_keyboard(user_id)
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=block_message,
            reply_markup=keyboard
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=block_message,
            reply_markup=keyboard
        )

# Обработка неизвестных команд - ИСПРАВЛЕННЫЙ ВАРИАНТ
@dp.message(F.text & F.text.startswith('/'))
async def unknown_command_handler(message: types.Message):
    user_id = message.from_user.id
    
    # Пропускаем известные команды
    known_commands = ['/start', '/admin', '/block', '/unblock', '/blocked']
    if any(message.text.startswith(cmd) for cmd in known_commands):
        return
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        await message.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    lang = get_user_language(user_id)
    if not lang:
        await send_language_selection(message.chat.id)
        return
    
    await send_main_menu(message.chat.id, user_id)

# ОБРАБОТКА СООБЩЕНИЙ
@dp.message(F.text)
async def handle_text_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, находится ли пользователь в состоянии обжалования
    if user_states.get(user_id, {}).get('waiting_for_appeal'):
        await process_appeal_message(message)
        return
    
    # Проверяем, находится ли администратор в состоянии ввода причины разблокировки
    if user_id == ADMIN_ID and user_states.get(ADMIN_ID, {}).get('waiting_for_unblock_reason'):
        await process_unblock_reason(message)
        return
    
    # Проверяем, находится ли пользователь в состоянии ожидания сообщения
    if user_id in user_states and user_states[user_id].get("waiting_for_message"):
        await process_user_message(message)
        return
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        await message.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    lang = get_user_language(user_id)
    if not lang:
        await send_language_selection(message.chat.id)
        return
    
    # Если нет активных состояний, показываем главное меню
    await send_main_menu(message.chat.id, user_id)

@dp.message(F.photo | F.document | F.animation)
async def handle_media_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, находится ли пользователь в состоянии обжалования
    if user_states.get(user_id, {}).get('waiting_for_appeal'):
        await process_appeal_message(message)
        return
    
    # Проверяем, находится ли пользователь в состоянии ожидания сообщения
    if user_id in user_states and user_states[user_id].get("waiting_for_message"):
        await process_user_message(message)
        return
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        await message.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    lang = get_user_language(user_id)
    if not lang:
        await send_language_selection(message.chat.id)
        return
    
    # Если нет активных состояний, показываем главное меню
    await send_main_menu(message.chat.id, user_id)

@dp.message(F.sticker)
async def handle_sticker_messages(message: types.Message):
    user_id = message.from_user.id
    
    # Проверяем, находится ли пользователь в состоянии обжалования
    if user_states.get(user_id, {}).get('waiting_for_appeal'):
        lang = get_user_language(user_id) or "ru"
        await message.answer(TEXTS[lang]["sticker_not_allowed"])
        return
    
    # Проверяем, находится ли пользователь в состоянии ожидания сообщения
    if user_id in user_states and user_states[user_id].get("waiting_for_message"):
        await process_user_message(message)
        return
    
    # Если пользователь заблокирован, показываем сообщение о блокировке
    if user_blocker.is_blocked(user_id):
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        keyboard = blocked_user_keyboard(user_id)
        await message.answer(block_message, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return
    
    lang = get_user_language(user_id)
    if not lang:
        await send_language_selection(message.chat.id)
        return
    
    # Если нет активных состояний, показываем главное меню
    await send_main_menu(message.chat.id, user_id)

async def process_appeal_message(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id) or "ru"
    
    block_info = user_blocker.get_block_info(user_id)
    if not block_info:
        await message.answer("❌ Вы не заблокированы.")
        return
    
    # Устанавливаем статус обжалования
    user_blocker.update_appeal_status(user_id, 'pending')
    
    # Убираем состояние ожидания
    user_states[user_id] = {}
    
    # Уведомляем администратора
    blocked_at = datetime.fromisoformat(block_info['blocked_at'])
    formatted_time = blocked_at.strftime("%d.%m.%Y | %H:%M:%S")
    
    appeal_header = (
        "📨 <b>НОВОЕ ОБЖАЛОВАНИЕ БЛОКИРОВКИ</b>\n\n"
        f"<b>Пользователь:</b> <code>{user_id}</code> ({block_info['username']})\n"
        f"<b>Имя:</b> {block_info['first_name']}\n"
        f"<b>Фамилия:</b> {block_info.get('last_name', 'Не указана')}\n"
        f"<b>Дата блокировки:</b> {formatted_time}\n"
        f"<b>Причина блокировки:</b> {block_info['reason']}\n"
        f"<b>Заблокировал:</b> {block_info['blocked_by']}\n\n"
        "<b>Текст обжалования:</b>\n"
    )

    try:
        if message.text:
            full_text = f"{appeal_header}\n{message.text}"
            await bot.send_message(ADMIN_ID, full_text, parse_mode=ParseMode.HTML)
        elif message.photo:
            caption = f"{appeal_header}\n{message.caption}" if message.caption else appeal_header
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.document:
            caption = f"{appeal_header}\n{message.caption}" if message.caption else appeal_header
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif message.animation:
            caption = f"{appeal_header}\n{message.caption}" if message.caption else appeal_header
            await bot.send_animation(ADMIN_ID, message.animation.file_id, caption=caption, parse_mode=ParseMode.HTML)

        # Показываем пользователю сообщение об успешной отправке
        await message.answer(
            TEXTS[lang]["appeal_sent"],
            reply_markup=appeal_back_keyboard(user_id)
        )
        
    except Exception as e:
        print(f"Ошибка при отправке обжалования: {e}")
        await message.answer(
            "❌ Произошла ошибка при отправке обжалования. Попробуйте еще раз.",
            reply_markup=appeal_back_keyboard(user_id)
        )

async def process_unblock_reason(message: types.Message):
    """Обработка причины разблокировки от администратора"""
    user_id = ADMIN_ID
    state = user_states.get(user_id, {})
    
    if not state.get('waiting_for_unblock_reason'):
        return
    
    target_user_id = state.get('unblock_user_id')
    from_page = state.get('unblock_from_page')
    reason = message.text
    
    # Разблокируем пользователя с причиной
    result, user_data = user_blocker.unblock_user(target_user_id, reason)
    
    # Очищаем состояние
    user_states[user_id] = {}
    
    # Показываем сообщение об успешной разблокировке без кнопки "Назад"
    text = TEXTS["ru"]["unblock_success"]
    
    await bot.send_message(
        message.chat.id,
        text,
        reply_markup=None  # Убрана клавиатура
    )
    
    # Уведомляем пользователя
    if user_data:
        try:
            lang = get_user_language(int(target_user_id)) or "ru"
            await bot.send_message(
                int(target_user_id), 
                TEXTS[lang]["unblocked"].format(reason=reason), 
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Не удалось уведомить пользователя {target_user_id}: {e}")

async def process_user_message(message: types.Message):
    user_id = message.from_user.id
    lang = get_user_language(user_id)
    message_type = user_states[user_id].get("message_type", "regular")
    current_time = time.time()
    
    action = None
    if message_type == "regular":
        action = "write_msg"
    elif message_type == "bug":
        action = "report_bug"
    
    if action and not check_cooldown(user_id, action, current_time):
        remaining = get_remaining_cooldown(user_id, action, current_time)
        await message.answer(
            TEXTS[lang]["cooldown_message"].format(remaining=remaining),
            reply_markup=back_keyboard(user_id)
        )
        return
    
    try:
        headers = {
            "regular": "💌 НОВОЕ СООБЩЕНИЕ",
            "suspicious": "🚨 СООБЩЕНИЕ О СБ", 
            "bug": "🐞 СООБЩЕНИЕ ОБ ОШИБКЕ"
        }

        admin_text = (
            f"{headers[message_type]}\n"
            f"👤 Имя: {message.from_user.full_name}\n"
            f"🔗 Юзернейм: @{message.from_user.username if message.from_user.username else 'отсутствует'}\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"📅 Время: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            "────────────────────"
        )

        if message.text:
            full_text = f"{admin_text}\n\n{message.text}"
            await bot.send_message(ADMIN_ID, full_text)
        elif message.photo:
            caption = f"{admin_text}\n\n{message.caption}" if message.caption else admin_text
            await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=caption)
        elif message.document:
            caption = f"{admin_text}\n\n{message.caption}" if message.caption else admin_text
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=caption)
        elif message.sticker:
            if message_type == "regular":
                await bot.send_sticker(ADMIN_ID, message.sticker.file_id)
                await bot.send_message(ADMIN_ID, admin_text)
            else:
                await message.answer(TEXTS[lang]["sticker_not_allowed"])
                return
        elif message.animation:
            caption = f"{admin_text}\n\n{message.caption}" if message.caption else admin_text
            await bot.send_animation(ADMIN_ID, message.animation.file_id, caption=caption)

        if action:
            user_cooldowns[f"{user_id}_{action}"] = current_time

        # Сбрасываем состояние ДО отправки ответа пользователю
        if user_id in user_states:
            user_states[user_id] = {}

        # Отправляем сообщение об успехе без кнопки "Назад"
        success_message = await message.answer(TEXTS[lang]["message_sent"])

        # Ждем 5 секунд и отправляем приветственное сообщение
        await asyncio.sleep(5)
        await send_main_menu(message.chat.id, user_id)

    except Exception as e:
        print(f"Ошибка при пересылке сообщения: {e}")
        # Сбрасываем состояние даже при ошибке
        if user_id in user_states:
            user_states[user_id] = {}
        await message.answer(
            TEXTS[lang]["error_sending"],
            reply_markup=back_keyboard(user_id)
        )

@dp.callback_query(F.data.startswith("appeal_approve_"))
async def appeal_approve_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Разблокируем пользователя
    result, user_data = user_blocker.unblock_user(user_id, "Обжалование принято")
    
    text = TEXTS["ru"]["unblock_success"]
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=text,
            reply_markup=None  # Убрана клавиатура
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=text,
            reply_markup=None  # Убрана клавиатура
        )
    
    # Уведомляем пользователя
    if user_data:
        try:
            lang = get_user_language(user_id) or "ru"
            await bot.send_message(
                user_id, 
                TEXTS[lang]["unblocked"].format(reason="Обжалование принято"), 
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            print(f"Не удалось уведомить пользователя {user_id}: {e}")

@dp.callback_query(F.data.startswith("appeal_reject_"))
async def appeal_reject_handler(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ У вас нет прав для использования этой функции.", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[2])
    
    # Обновляем статус обжалования
    user_blocker.update_appeal_status(user_id, 'rejected')
    
    if callback.message.photo:
        await safe_edit_message_caption(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            caption=f"❌ Обжалование пользователя {user_id} отклонено.\nПользователь не сможет подать повторное обжалование.",
            reply_markup=admin_panel_keyboard()
        )
    else:
        await safe_edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=callback.message.message_id,
            text=f"❌ Обжалование пользователя {user_id} отклонено.\nПользователь не сможет подать повторное обжалование.",
            reply_markup=admin_panel_keyboard()
        )
    
    # Уведомляем пользователя
    block_info = user_blocker.get_block_info(user_id)
    if block_info:
        lang = get_user_language(user_id) or "ru"
        block_message = user_blocker.format_block_message(user_id, lang)
        try:
            await bot.send_message(user_id, block_message, parse_mode=ParseMode.HTML)
        except Exception as e:
            print(f"Не удалось уведомить пользователя {user_id}: {e}")

async def main():
    try:
        print("Бот запускается...")
        print(f"Загружено {len(user_blocker.get_blocked_list())} заблокированных пользователей")
        print(f"Загружено {len(language_manager.get_all_users())} пользователей с выбором языка")
        
        await dp.start_polling(bot)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Бот остановлен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")
    except Exception as e:
        print(f"Ошибка при запуске: {e}")
        import traceback
        traceback.print_exc()

    input("Нажмите Enter для выхода...")
