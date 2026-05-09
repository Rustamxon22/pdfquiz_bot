import os
import random
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from states import QuizState
from pdf_reader import extract_text
from parser import parse_quiz

# ====================== TOKEN VA SOZLAMALAR ======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! .env faylida qo'shing.")

# ====================== ADMIN ID ======================
ADMIN_ID = 8426526387   # ← O'Z TELEGRAM ID INGIZNI YOZING!

bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

user_data = {}
paid_users = set()
pending_checks = {}

# ====================== TO'LOV MA'LUMOTLARI ======================
KARTA_RAQAMI = "5614 6830 3139 7854"
KARTA_ISM    = "Saidaxmedov Rustamjon"
TOlov_SUMMA  = "10 000 so'm"

# ====================== MENU ======================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="/start")],
        [KeyboardButton(text="/restart")],
        [KeyboardButton(text="/stop")],
    ],
    resize_keyboard=True
)


# ====================== START ======================
@dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()

    if user_id in paid_users:
        await message.answer(
            "👋 <b>Xush kelibsiz!</b>\n\n"
            "Siz cheksiz rejimdasiz ✅\n\n"
            "Quiz boshlash uchun PDF faylni yuboring."
        )
        await state.set_state(QuizState.waiting_pdf)
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
""")
        await message.answer("📤 PDF ni yuboring...", reply_markup=main_menu)
        return

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
    await message.answer(text)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ To'lov qildim, chek yuboraman", callback_data="send_check")]
    ])

    await message.answer(
        "To'lovni amalga oshirgandan keyin pastdagi tugmani bosing va chek rasmini yuboring 👇",
        reply_markup=keyboard
    )


# ====================== CALLBACK: CHEK YUBORAMAN ======================
@dp.callback_query(F.data == "send_check")
async def paid_check_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "📸 Iltimos, to'lov cheki rasmini yuboring.\n"
        "Admin tekshirib, tez orada tasdiqlaydi."
    )


# ====================== CHEK (RASM) QABUL QILISH ======================
@dp.message(F.photo)
async def handle_payment_check(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    if user_id in paid_users:
        await message.answer("ℹ️ Siz allaqachon tasdiqlangansiz. PDF faylni yuboring.")
        return

    photo_id = message.photo[-1].file_id
    pending_checks[user_id] = {
        "file_id":   photo_id,
        "username":  message.from_user.username or "Noma'lum",
        "full_name": message.from_user.full_name,
        "user_id":   user_id,
    }

    await message.answer(
        "⏳ <b>Chekingiz qabul qilindi!</b>\n\n"
        "Admin tekshirib, tez orada tasdiqlaydi.\n"
        "Odatda 5-15 daqiqa ichida javob beriladi."
    )

    admin_keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Rad etish",  callback_data=f"reject_{user_id}")
        ]
    ])

    username_show = message.from_user.username or "Nomalum"

    admin_text = (
        "💳 <b>Yangi to'lov cheki!</b>\n\n"
        f"👤 Ism: <b>{message.from_user.full_name}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"📛 Username: @{username_show}\n\n"
        "Quyida tasdiqlash yoki rad etish tugmasini bosing 👇"
    )

    await bot.send_photo(
        chat_id=ADMIN_ID,
        photo=photo_id,
        caption=admin_text,
        reply_markup=admin_keyboard
    )


# ====================== ADMIN: TASDIQLASH ======================
@dp.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])
    paid_users.add(user_id)

    if user_id in pending_checks:
        del pending_checks[user_id]

    await callback.message.edit_caption(
        caption=(callback.message.caption or "") + "\n\n✅ <b>TASDIQLANDI</b>",
        parse_mode="HTML"
    )
    await callback.answer("✅ Foydalanuvchi tasdiqlandi!")

    await bot.send_message(
        user_id,
        "🎉 <b>To'lovingiz tasdiqlandi!</b>\n\n"
        "Endi siz <b>cheksiz rejimdasiz</b> ✅\n\n"
        "Quiz yaratish uchun PDF faylni yuboring."
    )

    await bot.send_message(
        user_id,
        """📤 <b>PDF faylni yuboring.</b>

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
- ==== — savol va variantlarni ajratadi
- ++++ — savollar orasini ajratadi
- # — to'g'ri javob oldiga qo'yiladi (faqat bittasiga)"""
    )

    # ✅ TO'G'RILANGAN QISM
    bot_info = await bot.get_me()
    storage_key = StorageKey(
        bot_id=bot_info.id,
        chat_id=user_id,
        user_id=user_id
    )
    user_state = FSMContext(storage=dp.storage, key=storage_key)
    await user_state.set_state(QuizState.waiting_pdf)


# ====================== ADMIN: RAD ETISH ======================
@dp.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    user_id = int(callback.data.split("_")[1])

    if user_id in pending_checks:
        del pending_checks[user_id]

    await callback.message.edit_caption(
        (callback.message.caption or "") + "\n\n❌ <b>RAD ETILDI</b>"
    )
    await callback.answer("❌ Rad etildi.")

    await bot.send_message(
        user_id,
        "❌ <b>To'lovingiz tasdiqlanmadi.</b>\n\n"
        "Sabab: Chek noto'g'ri yoki to'lov amalga oshmagan.\n\n"
        f"Iltimos, <b>{TOlov_SUMMA}</b> miqdorida to'lov qiling va chekni qayta yuboring.\n"
        f"💳 Karta: <code>{KARTA_RAQAMI}</code>"
    )


# ====================== ADMIN BUYRUQLARI ======================
@dp.message(Command("users"))
async def admin_users(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not paid_users:
        await message.answer("Hali tasdiqlangan foydalanuvchi yo'q.")
        return
    text = f"✅ Tasdiqlangan foydalanuvchilar: <b>{len(paid_users)} ta</b>\n\n"
    text += "\n".join([f"• <code>{uid}</code>" for uid in paid_users])
    await message.answer(text)


@dp.message(Command("pending"))
async def admin_pending(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not pending_checks:
        await message.answer("Hozircha kutilayotgan chek yo'q.")
        return
    text = f"⏳ Kutilayotgan cheklar: <b>{len(pending_checks)} ta</b>\n\n"
    for uid, info in pending_checks.items():
        text += f"• {info['full_name']} (@{info['username']}) — ID: <code>{uid}</code>\n"
    await message.answer(text)


# ====================== PDF QABUL QILISH ======================
@dp.message(F.document, QuizState.waiting_pdf)
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
        await state.set_state(QuizState.asking_num_questions)

    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi: {str(e)}")


# ====================== RESTART / STOP ======================
@dp.message(Command("restart"))
async def restart_cmd(message: types.Message, state: FSMContext):
    await start_cmd(message, state)


@dp.message(Command("stop"))
async def stop_cmd(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id in user_data:
        user_data[user_id]["stopped"] = True
        del user_data[user_id]
    await state.clear()
    await message.answer("🛑 Test to'xtatildi.\nYangi test uchun /start bosing.", reply_markup=main_menu)


# ====================== SAVOL SONI ======================
@dp.message(QuizState.asking_num_questions)
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
        user["questions"]      = selected
        user["total_selected"] = num

        await message.answer(
            f"✅ {num} ta savol tanlandi.\n\n"
            f"⏱ Har bir savolga nechta sekund vaqt beraylik? (masalan: 30)"
        )
        await state.set_state(QuizState.asking_time)

    except ValueError:
        await message.answer("❌ Faqat butun son kiriting.")


# ====================== VAQT ======================
@dp.message(QuizState.asking_time)
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

        await state.set_state(QuizState.in_quiz)
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

    user["current_correct_index"]    = correct_new_index
    user["current_shuffled_options"] = shuffled_options
    user["current_question_text"]    = q["question"]
    user["answered"]                 = False

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
        f"📊 Joriy natija: <b>{user['score']}/{total_answered}</b> ({current_percent}%)"
    )

    if user["index"] < len(user.get("questions", [])):
        await asyncio.sleep(1.5)
        await send_question(chat_id, user_id)
    else:
        await finish_quiz(chat_id, user_id)


# ====================== JAVOB HANDLER ======================
@dp.poll_answer()
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
        f"📊 Joriy natija: <b>{user['score']}/{total_answered}</b> ({current_percent}%)"
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
        reply_markup=main_menu
    )

    if user_id in user_data:
        del user_data[user_id]


# ====================== BOTNI ISHGA TUSHIRISH ======================
async def main():
    print("🚀 Quiz Bot ishga tushdi...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
