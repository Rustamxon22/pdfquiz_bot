import random
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

from states import QuizState
from pdf_reader import extract_text
from parser import parse_quiz

BOT_TOKEN = "8741827603:AAGRHR0HyDhfGL-8nAOYWfu_6kb2rWvbhd8"

bot = Bot(token=BOT_TOKEN)
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
        parse_mode="HTML",
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

        file = await message.document.download()
        text = extract_text(file.name)
        questions = parse_quiz(text)

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
            parse_mode="HTML",
            reply_markup=main_menu
        )
        await message.answer("🔢 Nechta savol bilan test o‘tkazmoqchisiz? (masalan: 10)")
        await QuizState.asking_num_questions.set()

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


# ====================== NECHTA SAVOL ======================
@dp.message_handler(state=QuizState.asking_num_questions)
async def ask_num_questions(message: types.Message, state: FSMContext):
    user = user_data.get(message.from_user.id)
    if not user: return
    try:
        num = int(message.text)
        total = len(user["all_questions"])
        if num < 1 or num > total:
            await message.answer(f"1 dan {total} gacha son kiriting.")
            return
        selected = user["all_questions"][:num]
        random.shuffle(selected)
        user["questions"] = selected
        user["total_selected"] = num
        await message.answer(f"✅ {num} ta savol tanlandi.\n\n⏱ Har bir savolga nechta sekund? (masalan: 30)")
        await QuizState.asking_time.set()
    except:
        await message.answer("Faqat raqam kiriting.")


# ====================== VAQT SO‘RASH ======================
@dp.message_handler(state=QuizState.asking_time)
async def ask_time_per_question(message: types.Message, state: FSMContext):
    user = user_data.get(message.from_user.id)
    if not user: return
    try:
        sec = int(message.text)
        if sec < 5 or sec > 300:
            await message.answer("5-300 oralig‘ida son kiriting.")
            return
        user["time_per_question"] = sec
        await message.answer(f"✅ Vaqt belgilandi: {sec} sekund.\n\nTest boshlanmoqda...")
        await QuizState.in_quiz.set()
        await send_question(message.chat.id, message.from_user.id)
    except:
        await message.answer("Faqat raqam kiriting.")


# ====================== SAVOL YUBORISH (Native Quiz Poll) ======================
async def send_question(chat_id: int, user_id: int):
    user = user_data.get(user_id)
    if not user or user.get("stopped"):
        return

    if user["index"] >= len(user.get("questions", [])):
        await finish_quiz(chat_id, user_id)
        return

    q = user["questions"][user["index"]]
    time_limit = user["time_per_question"]

    options = q["options"].copy()
    correct_answer = q.get("correct")

    indexed = list(enumerate(options))
    random.shuffle(indexed)
    shuffled_options = [opt for _, opt in indexed]
    correct_new_index = next(i for i, (_, opt) in enumerate(indexed) if opt == correct_answer)

    user["current_correct_index"] = correct_new_index
    user["current_shuffled_options"] = shuffled_options
    user["current_question_text"] = q["question"]

    safe_options = [opt[:100] for opt in shuffled_options]

    try:
        poll = await bot.send_poll(
            chat_id=chat_id,
            question=f"❓ Savol {user['index'] + 1}/{user['total_selected']}\n{q['question']}",
            options=safe_options,
            type="quiz",
            correct_option_id=correct_new_index,
            is_anonymous=False,
            open_period=time_limit,
            explanation=f"✅ To'g'ri javob: {correct_answer}"
        )
        user["current_poll_id"] = poll.poll.id
        user["current_message_id"] = poll.message_id
        user["current_chat_id"] = chat_id
    except Exception as e:
        await bot.send_message(chat_id, f"Poll yuborishda xatolik: {e}")


# ====================== POLL JAVOBI ======================
@dp.poll_answer_handler()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    user_id = poll_answer.user.id
    user = user_data.get(user_id)
    if not user or user.get("stopped"):
        return

    chosen_index = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    correct_idx = user.get("current_correct_index", -1)

    if chosen_index == correct_idx:
        user["score"] += 1

    total_answered = user["index"] + 1
    current_percent = round((user["score"] / total_answered) * 100, 1)

    await bot.send_message(
        user["current_chat_id"],
        f"📊 Joriy natija: <b>{user['score']}/{total_answered}</b> ({current_percent}%)",
        parse_mode="HTML"
    )

    user["index"] += 1

    if user["index"] < len(user.get("questions", [])):
        await asyncio.sleep(1.8)
        await send_question(user["current_chat_id"], user_id)
    else:
        await finish_quiz(user["current_chat_id"], user_id)


# ====================== TEST TUGASHI ======================
async def finish_quiz(chat_id: int, user_id: int):
    user = user_data.get(user_id)
    if not user: return

    total = user["total_selected"]
    score = user["score"]
    percent = round((score / total) * 100, 1) if total > 0 else 0

    await bot.send_message(
        chat_id,
        f"🎉 <b>Test tugadi!</b>\n\n"
        f"To‘g‘ri javoblar: <b>{score}</b>/{total}\n"
        f"Natija: <b>{percent}%</b>",
        parse_mode="HTML",
        reply_markup=main_menu
    )

    if user_id in user_data:
        del user_data[user_id]


# ====================== ISHGA TUSHIRISH ======================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)