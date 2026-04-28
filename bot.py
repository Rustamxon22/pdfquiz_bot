import os
import random
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

from states import QuizState
from pdf_reader import extract_text
from parser import parse_quiz

# ====================== TOKEN ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! .env faylida yoki Railway Variables da qo'shing.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_data = {}

# ====================== MENU ======================
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("/start"))
main_menu.add(KeyboardButton("/restart"))
main_menu.add(KeyboardButton("/stop"))


# ====================== START ======================
@dp.message_handler(commands=['start'], state='*')
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in user_data:
        del user_data[user_id]

    await state.finish()

    pdf_example = (
        "📄 <b>PDF fayl quyidagi formatda bo‘lishi kerak:</b>\n\n"
        "<code>"
        "Raqamli elektronikaning asosiy ustunligi nimada\n"
        "====\n"
        "#Shovqinga kam sezuvchanlik\n"
        "====\n"
        "Signalni doimiy kuchaytirish\n"
        "====\n"
        "Mexanik kuchini oshirish\n"
        "====\n"
        "Haroratni avtomatik boshqarish\n"
        "++++\n\n"
        "Keyingi savol...\n"
        "++++"
        "</code>"
    )

    await message.answer(
        "👋 Salom! Men PDF dan quiz yarataman.\n\n"
        + pdf_example +
        "\n\n📤 Endi PDF faylni yuboring.",
        reply_markup=main_menu
    )
    await QuizState.waiting_pdf.set()


@dp.message_handler(commands=['restart'], state='*')
async def restart_cmd(message: types.Message, state: FSMContext):
    await start_cmd(message, state)


@dp.message_handler(commands=['stop'], state='*')
async def stop_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in user_data:
        user_data[user_id]["stopped"] = True
        del user_data[user_id]
    await state.finish()
    await message.answer("🛑 Test to‘xtatildi.\nYangi test uchun /start bosing.", reply_markup=main_menu)
    await QuizState.waiting_pdf.set()


# ====================== PDF QABUL ======================
@dp.message_handler(content_types=['document'], state=QuizState.waiting_pdf)
async def handle_pdf(message: types.Message, state: FSMContext):
    try:
        await message.answer("📤 PDF yuklanmoqda, biroz kuting...")

        # Faylni yuklab olish
        file_info = await bot.get_file(message.document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        
        # Vaqtinchalik fayl sifatida saqlash
        file_name = f"temp_{message.document.file_id}.pdf"
        with open(file_name, "wb") as f:
            f.write(downloaded_file.getvalue())

        text = extract_text(file_name)
        questions = parse_quiz(text)

        # Vaqtinchalik faylni o‘chirish
        if os.path.exists(file_name):
            os.remove(file_name)

        if not questions:
            await message.answer("❌ PDFdan savollar topilmadi.\nFormatni tekshiring va qayta yuboring.")
            return

        user_id = message.from_user.id
        user_data[user_id] = {
            "all_questions": questions,
            "questions": [],
            "index": 0,
            "score": 0,
            "total_selected": 0,
            "time_per_question": 30,
            "stopped": False,
            "current_chat_id": message.chat.id
        }

        await message.answer(
            f"✅ PDF muvaffaqiyatli o‘qildi!\n"
            f"📊 Topilgan savollar soni: <b>{len(questions)} ta</b>",
            reply_markup=main_menu
        )
        await message.answer("🔢 Nechta savol bilan test o‘tkazmoqchisiz? (masalan: 10)")
        await QuizState.asking_num_questions.set()

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


# Qolgan qismlar (ask_num_questions, ask_time_per_question, send_question, 
# handle_poll_answer, finish_quiz) o‘zgarmadi. Ularni avvalgi kodingizdan qoldiring.

# ====================== ISHGA TUSHIRISH (Railway uchun to‘g‘rilangan) ======================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)