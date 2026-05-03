import os
import random
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

from states import QuizState
from pdf_reader import extract_text
from parser import parse_quiz

# ====================== TOKEN VA SOZLAMALAR ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! .env faylida qo'shing.")

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

user_data = {}
paid_users = set()   # Bir marta to'lov qilgan foydalanuvchilar (doimiy saqlanadi)

# ====================== TO'LOV MA'LUMOTLARI ======================
KARTA_RAQAMI = "5614 6830 3139 7854"   # ← O'Z KARTANGIZNI YOZING!
KARTA_ISM    = "Saidaxmedov Rustamjon"             
TOlov_SUMMA  = "10 000 so'm"

# ====================== MENU ======================
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("/start"))
main_menu.add(KeyboardButton("/restart"))
main_menu.add(KeyboardButton("/stop"))


# ====================== START ======================
@dp.message_handler(commands=['start'], state='*')
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.finish()

    # Agar allaqachon to'lov qilgan bo'lsa
    if user_id in paid_users:
        await message.answer(
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "Siz cheksiz rejimdasiz ✅\n\n"
            "Quiz boshlash uchun PDF faylni yuboring.",
            parse_mode="HTML"
        )
        await QuizState.waiting_pdf.set()
        
        await message.answer("""
📤 <b>PDF faylni yuboring.</b>

Format eslatmasi:
Savol matni
====
#To'g'ri javob
====
Variant 2
====
Variant 3
====
Variant 4
++++
Keyingi savol...
""", parse_mode="HTML")
        
        await message.answer("📤 PDF ni yuboring...", reply_markup=main_menu)
        return

    # To'lov qilmagan foydalanuvchi
    if user_id in user_data:
        del user_data[user_id]

    text = f"""
👋 <b>Salom! PDF dan Quiz yaratuvchi botga xush kelibsiz!</b>

<b>Cheksiz foydalanish uchun:</b>
💰 Bir martalik to'lov: <b>{TOlov_SUMMA}</b>

💳 <b>Karta raqami:</b> <code>{KARTA_RAQAMI}</code>
👤 <b>Ism:</b> {KARTA_ISM}

✅ Pulni o'tkazib bo'lgach, <b>chek rasmini</b> shu yerga yuboring.
"""
    await message.answer(text, parse_mode="HTML")

    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("✅ To'lov qildim, chek yuboraman", callback_data="send_check"))

    await message.answer(
        "To'lovni amalga oshirgandan keyin pastdagi tugmani bosing va chek rasmini yuboring 👇",
        reply_markup=keyboard
    )


# ====================== CHEK (RASM) QABUL QILISH ======================
@dp.message_handler(content_types=['photo'], state='*')
async def handle_payment_check(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    paid_users.add(user_id)   # To'lov qilgan sifatida belgilaymiz

    await message.answer(
        "✅ <b>To'lov qabul qilindi!</b>\n\n"
        "Siz endi <b>cheksiz rejimdasiz</b> 🎉\n\n"
        "Quiz yaratish uchun PDF faylni yuboring.",
        parse_mode="HTML"
    )
    
    await QuizState.waiting_pdf.set()
    
    pdf_format_text = """
📤 <b>Endi PDF faylni yuboring.</b>
Bot avtomatik ravishda quiz yaratadi.

📄 PDF faylni quyidagi formatda tayyorlang:

Savol matni
====
#To'g'ri javob
====
Variant 2
====
Variant 3
====
Variant 4
++++
Keyingi savol matni
====
...
++++

📌 <b>Qoidalar:</b>
• ==== — savol va variantlarni ajratadi
• ++++ — savollar orasini ajratadi (oxirida ham bo‘lishi shart)
• # — to'g'ri javob oldiga qo‘yiladi (faqat bittasiga)
• Variantlar istalgan tartibda yoziladi — bot o‘zi aralashtiradi
"""
    await message.answer(pdf_format_text, parse_mode="HTML")
    await message.answer("📤 PDF faylni yuborishingiz mumkin...", reply_markup=main_menu)


@dp.callback_query_handler(lambda c: c.data == "send_check")
async def paid_check_callback(callback: types.CallbackQuery):
    await callback.answer("Chek rasmini yuboring ✅", show_alert=False)


# ====================== PDF QABUL QILISH ======================
@dp.message_handler(content_types=['document'], state=QuizState.waiting_pdf)
async def handle_pdf(message: types.Message, state: FSMContext):
    try:
        await message.answer("📤 PDF yuklanmoqda, biroz kuting...")

        file_info = await bot.get_file(message.document.file_id)
        downloaded_file = await bot.download_file(file_info.file_path)

        file_name = f"temp_{message.document.file_id}.pdf"
        with open(file_name, "wb") as f:
            f.write(downloaded_file.getvalue())

        text = extract_text(file_name)
        questions = parse_quiz(text)

        if os.path.exists(file_name):
            os.remove(file_name)

        if not questions:
            await message.answer("❌ PDFdan savollar topilmadi.\nFormatni tekshiring va qayta yuboring.")
            return

        user_id = message.from_user.id
        user_data[user_id] = {
            "all_questions":      questions,
            "questions":          [],
            "index":              0,
            "score":              0,
            "total_selected":     0,
            "time_per_question":  30,
            "stopped":            False,
            "answered":           False,
            "current_poll_id":    None,
            "current_chat_id":    message.chat.id,
        }

        await message.answer(
            f"✅ PDF muvaffaqiyatli o'qildi!\n"
            f"📊 Topilgan savollar soni: <b>{len(questions)} ta</b>",
            reply_markup=main_menu
        )
        await message.answer("🔢 Nechta savol bilan test o'tkazmoqchisiz? (masalan: 10)")
        await QuizState.asking_num_questions.set()

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


# ====================== RESTART / STOP ======================
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
    await message.answer("🛑 Test to'xtatildi.\nYangi test uchun /start bosing.", reply_markup=main_menu)


# ====================== QOLGAN KOD (o'zgartirilmagan) ======================
# ... (SAVOL SONI, VAQT, SAVOL YUBORISH, TIMEOUT, JAVOB HANDLER, FINISH_QUIZ) ...

# ====================== SAVOL SONI ======================
@dp.message_handler(state=QuizState.asking_num_questions)
async def ask_num_questions(message: types.Message, state: FSMContext):
    user = user_data.get(message.from_user.id)
    if not user:
        return
    try:
        num = int(message.text)
        total = len(user["all_questions"])
        if num < 1 or num > total:
            await message.answer(f"1 dan {total} gacha son kiriting.")
            return

        selected = user["all_questions"][:num]
        random.shuffle(selected)
        user["questions"]       = selected
        user["total_selected"]  = num

        await message.answer(
            f"✅ {num} ta savol tanlandi.\n\n"
            f"⏱ Har bir savolga nechta sekund vaqt beraylik? (masalan: 30)"
        )
        await QuizState.asking_time.set()

    except ValueError:
        await message.answer("❌ Faqat butun son kiriting.")


# ====================== VAQT ======================
@dp.message_handler(state=QuizState.asking_time)
async def ask_time_per_question(message: types.Message, state: FSMContext):
    user = user_data.get(message.from_user.id)
    if not user:
        return
    try:
        sec = int(message.text)
        if sec < 5 or sec > 300:
            await message.answer("5 dan 300 gacha son kiriting.")
            return

        user["time_per_question"] = sec
        await message.answer(f"✅ Vaqt belgilandi: {sec} sekund.\n\nTest boshlanmoqda... 🎯")

        await QuizState.in_quiz.set()
        await send_question(message.chat.id, message.from_user.id)

    except ValueError:
        await message.answer("❌ Faqat butun son kiriting.")


# ====================== SAVOL YUBORISH ======================
async def send_question(chat_id: int, user_id: int):
    user = user_data.get(user_id)
    if not user or user.get("stopped"):
        return

    if user["index"] >= len(user.get("questions", [])):
        await finish_quiz(chat_id, user_id)
        return

    q          = user["questions"][user["index"]]
    time_limit = user["time_per_question"]

    options        = q["options"].copy()
    correct_answer = q.get("correct")

    indexed          = list(enumerate(options))
    random.shuffle(indexed)
    shuffled_options  = [opt for _, opt in indexed]
    correct_new_index = next(i for i, (_, opt) in enumerate(indexed) if opt == correct_answer)

    user["current_correct_index"]   = correct_new_index
    user["current_shuffled_options"] = shuffled_options
    user["current_question_text"]   = q["question"]
    user["answered"]                = False

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
        user["current_chat_id"] = chat_id

        asyncio.create_task(
            auto_next_on_timeout(chat_id, user_id, poll.poll.id, time_limit)
        )

    except Exception as e:
        await bot.send_message(chat_id, f"Poll yuborishda xatolik: {e}")


# ====================== TIMEOUT HANDLER ======================
async def auto_next_on_timeout(chat_id: int, user_id: int, poll_id: str, time_limit: int):
    await asyncio.sleep(time_limit + 1.5)

    user = user_data.get(user_id)
    if not user or user.get("stopped"):
        return
    if user.get("current_poll_id") != poll_id:
        return
    if user.get("answered"):
        return

    user["index"] += 1
    total_answered  = user["index"]
    current_percent = round((user["score"] / total_answered) * 100, 1) if total_answered > 0 else 0

    await bot.send_message(
        chat_id,
        f"⏱ Vaqt tugadi! Savol o'tkazib yuborildi.\n"
        f"📊 Joriy natija: <b>{user['score']}/{total_answered}</b> ({current_percent}%)",
        parse_mode="HTML"
    )

    if user["index"] < len(user.get("questions", [])):
        await asyncio.sleep(1.5)
        await send_question(chat_id, user_id)
    else:
        await finish_quiz(chat_id, user_id)


# ====================== JAVOB HANDLER ======================
@dp.poll_answer_handler()
async def handle_poll_answer(poll_answer: types.PollAnswer):
    user_id = poll_answer.user.id
    user    = user_data.get(user_id)
    if not user or user.get("stopped"):
        return

    user["answered"] = True

    chosen_index = poll_answer.option_ids[0] if poll_answer.option_ids else -1
    correct_idx  = user.get("current_correct_index", -1)

    if chosen_index == correct_idx:
        user["score"] += 1

    total_answered  = user["index"] + 1
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
    if not user:
        return

    total   = user["total_selected"]
    score   = user["score"]
    percent = round((score / total) * 100, 1) if total > 0 else 0

    await bot.send_message(
        chat_id,
        f"🎉 <b>Test tugadi!</b>\n\n"
        f"To'g'ri javoblar: <b>{score}</b>/{total}\n"
        f"Natija: <b>{percent}%</b>",
        parse_mode="HTML",
        reply_markup=main_menu
    )

    if user_id in user_data:
        del user_data[user_id]


# ====================== BOTNI ISHGA TUSHIRISH ======================
if __name__ == "__main__":
    print("🚀 Quiz Bot ishga tushdi...")
    executor.start_polling(dp, skip_updates=True)