import os
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
import aiohttp

# --- Получение токена и URL из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
PROFILE_URL = os.getenv("PROFILE_URL")

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
scheduler = AsyncIOScheduler()

user_data = {}

class SetTime(StatesGroup):
    waiting_for_morning = State()
    waiting_for_evening = State()

# --- Кнопки
main_kb = ReplyKeyboardMarkup(resize_keyboard=True)
main_kb.add(KeyboardButton("📊 Профиль"))
main_kb.add(KeyboardButton("⚙️ Настройка уведомлений"))

notif_kb = ReplyKeyboardMarkup(resize_keyboard=True)
notif_kb.add(KeyboardButton("Утренний"))
notif_kb.add(KeyboardButton("Вечерний"))
notif_kb.add(KeyboardButton("◀️ Назад"))

# --- Парсер сайта
async def get_profile_data():
    async with aiohttp.ClientSession() as session:
        async with session.get(PROFILE_URL) as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            spans = soup.find_all("span")
            coins_span = soup.find("span", class_="user-module-scss-module__aFNIja__coins")
            try:
                data = {
                    "total": spans[0].text.strip(),
                    "cash": spans[1].text.strip(),
                    "bank": spans[2].text.strip(),
                    "deposit": spans[3].text.strip(),
                    "coins": coins_span.text.strip() if coins_span else "0AZ",
                    "level": spans[5].text.strip(),
                    "xp": spans[6].text.strip(),
                    "status": spans[7].text.strip(),
                    "house": spans[8].text.strip(),
                    "house_tax": spans[9].text.strip()
                }
            except IndexError:
                # Если структура сайта поменялась, возвращаем пустые значения
                data = {
                    "total": "-", "cash": "-", "bank": "-", "deposit": "-",
                    "coins": "-", "level": "-", "xp": "-", "status": "-", "house": "-", "house_tax": "-"
                }
            return data

# --- /start
@dp.message_handler(commands=["start"])
async def cmd_start(message: types.Message):
    user_data[message.from_user.id] = {
        "morning": "06:00",
        "evening": "18:00",
        "nick": "Feliks_Hikikomori"
    }
    await message.reply("Привет! Я буду присылать твой отчёт утром и вечером.\nИспользуй кнопки ниже.", reply_markup=main_kb)

# --- Профиль
@dp.message_handler(lambda message: message.text == "📊 Профиль")
async def profile_button(message: types.Message):
    profile = await get_profile_data()
    now = datetime.now()
    if 5 <= now.hour < 12:
        greeting = "🌅 Доброе утро"
    elif 12 <= now.hour < 18:
        greeting = "☀️ Добрый день"
    else:
        greeting = "🌙 Добрый вечер"

    report = f"""
{greeting}, {user_data[message.from_user.id]['nick']}!

💰 Денежные средства:
— Наличка: {profile['cash']}
— В банке: {profile['bank']}
— На депозите: {profile['deposit']}
— Общая сумма: {profile['total']}

💠 AZ-coin: {profile['coins']}

🎮 Уровень: {profile['level']}
⭐ XP: {profile['xp']}
🏷️ Статус: {profile['status']}

🏠 Налоги на дом:
— {profile['house']}: {profile['house_tax']}
"""
    await message.reply(report, reply_markup=main_kb)

# --- Настройка уведомлений
@dp.message_handler(lambda message: message.text == "⚙️ Настройка уведомлений")
async def notif_button(message: types.Message):
    await message.reply("Выберите период для изменения времени:", reply_markup=notif_kb)

@dp.message_handler(lambda message: message.text == "Утренний")
async def set_morning(message: types.Message):
    await message.reply("Напишите новое время утреннего отчёта в формате HH:MM")
    await SetTime.waiting_for_morning.set()

@dp.message_handler(lambda message: message.text == "Вечерний")
async def set_evening(message: types.Message):
    await message.reply("Напишите новое время вечернего отчёта в формате HH:MM")
    await SetTime.waiting_for_evening.set()

@dp.message_handler(lambda message: message.text == "◀️ Назад")
async def back_main(message: types.Message):
    await message.reply("Возврат в главное меню", reply_markup=main_kb)

# --- FSM обработка времени
@dp.message_handler(state=SetTime.waiting_for_morning)
async def process_morning_time(message: types.Message, state: FSMContext):
    try:
        hr, mn = map(int, message.text.split(":"))
        user_data[message.from_user.id]["morning"] = f"{hr:02d}:{mn:02d}"
        await message.reply(f"Время утреннего отчёта установлено на {hr:02d}:{mn:02d}", reply_markup=main_kb)
        await state.finish()
        schedule_reports()
    except:
        await message.reply("Неверный формат! Используй HH:MM, например 06:30")

@dp.message_handler(state=SetTime.waiting_for_evening)
async def process_evening_time(message: types.Message, state: FSMContext):
    try:
        hr, mn = map(int, message.text.split(":"))
        user_data[message.from_user.id]["evening"] = f"{hr:02d}:{mn:02d}"
        await message.reply(f"Время вечернего отчёта установлено на {hr:02d}:{mn:02d}", reply_markup=main_kb)
        await state.finish()
        schedule_reports()
    except:
        await message.reply("Неверный формат! Используй HH:MM, например 18:30")

# --- Отправка отчёта
async def send_report(user_id):
    profile = await get_profile_data()
    now = datetime.now()
    if 5 <= now.hour < 12:
        greeting = "🌅 Доброе утро"
    elif 12 <= now.hour < 18:
        greeting = "☀️ Добрый день"
    else:
        greeting = "🌙 Добрый вечер"

    report = f"""
{greeting}, {user_data[user_id]['nick']}!

💰 Денежные средства:
— Наличка: {profile['cash']}
— В банке: {profile['bank']}
— На депозите: {profile['deposit']}
— Общая сумма: {profile['total']}

💠 AZ-coin: {profile['coins']}

🎮 Уровень: {profile['level']}
⭐ XP: {profile['xp']}
🏷️ Статус: {profile['status']}

🏠 Налоги на дом:
— {profile['house']}: {profile['house_tax']}
"""
    await bot.send_message(user_id, report)

# --- Планировщик
def schedule_reports():
    scheduler.remove_all_jobs()
    for user_id, times in user_data.items():
        hr, mn = map(int, times["morning"].split(":"))
        scheduler.add_job(lambda uid=user_id: asyncio.create_task(send_report(uid)), "cron", hour=hr, minute=mn)
        hr, mn = map(int, times["evening"].split(":"))
        scheduler.add_job(lambda uid=user_id: asyncio.create_task(send_report(uid)), "cron", hour=hr, minute=mn)

scheduler.start()

# --- Запуск
from aiogram import executor

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    schedule_reports()
    executor.start_polling(dp, skip_updates=True)
