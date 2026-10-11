import asyncio
import json
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import google.generativeai as genai
from pypdf import PdfReader

# ==================== KALITLAR ====================
BOT_TOKEN = "8800666543:AAEHWaftkv2oq9rfSS_W55Evrd6Sf3cFZJw"
GEMINI_API_KEY = "AQ.Ab8RN6LNizA-06SUiE92Omguq_Pmz9d3Uqljhc7MYqrItwNiRA"
# ===================================================

genai.configure(api_key=GEMINI_API_KEY)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class QuizForm(StatesGroup):
  waiting_for_pdf = State()
  waiting_for_pages = State()


def extract_text_from_pdf(pdf_path, start_page, end_page):
  reader = PdfReader(pdf_path)
  total_pages = len(reader.pages)
  start_page = max(1, start_page)
  end_page = min(total_pages, end_page)

  text = ""
  for page_num in range(start_page - 1, end_page):
    text += reader.pages[page_num].extract_text() or ""
  return text, total_pages


def generate_quiz_from_text(text):
  prompt = f"""
    Quyidagi matn asosida 5 ta ko'p tanlovli (quiz) test savoli tuzib ber.
    Javobni FAQAT quyidagi JSON formatida qaytar, boshqa hech qanday izoh qo'shma:
    [
        {{
            "question": "Savol matni",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "correct_option_id": 0
        }}
    ]

    Matn:
    {text[:6000]}
    """
  model = genai.GenerativeModel("gemini-2.5-flash")

  response = model.generate_content(prompt)

  clean_json = (
      response.text.replace("```json", "").replace("```", "").strip()
  )
  return json.loads(clean_json)


@dp.message(CommandStart())
async def start_cmd(message: types.Message, state: FSMContext):
  await state.clear()
  await message.answer(
      "Salom! Men kitob va konspektlardan test tuzuvchi botman.\n\nBoshlash"
      " uchun menga **PDF formatidagi** kitob yoki konspekt yuboring."
  )
  await state.set_state(QuizForm.waiting_for_pdf)


@dp.message(QuizForm.waiting_for_pdf, F.document)
async def handle_pdf(message: types.Message, state: FSMContext):
  if not message.document.file_name.endswith(".pdf"):
    await message.answer("Iltimos, faqat PDF fayl yuboring!")
    return

  msg = await message.answer("Fayl yuklanmoqda...")
  file = await bot.get_file(message.document.file_id)
  file_path = f"temp_{message.document.file_id}.pdf"
  await bot.download_file(file.file_path, file_path)

  reader = PdfReader(file_path)
  total_pages = len(reader.pages)
  await state.update_data(file_path=file_path, total_pages=total_pages)

  await msg.delete()
  await message.answer(
      f"Kitob qabul qilindi! Jami sahifalar soni: **{total_pages}**"
      " ta.\n\nQaysi sahifalardan test tuzay? (Masalan: `1-10` yoki `15-20`"
      " ko'rinishida yozing):"
  )
  await state.set_state(QuizForm.waiting_for_pages)


@dp.message(QuizForm.waiting_for_pages)
async def handle_pages(message: types.Message, state: FSMContext):
  user_input = message.text.strip()
  try:
    start_p, end_p = map(int, user_input.split("-"))
  except ValueError:
    await message.answer(
        "Iltimos, sahifalarni to'g'ri formatda kiriting! Masalan: `1-10`"
    )
    return

  data = await state.get_data()
  file_path = data.get("file_path")
  msg = await message.answer("Sahifalar tahlil qilinmoqda va AI testlar tuzmoqda...")

  try:
    text, total_pages = extract_text_from_pdf(file_path, start_p, end_p)
    if not text.strip():
      await message.answer(
          "Tanlangan sahifalardan matn o'qib bo'lmadi (skanerlangan rasm"
          " bo'lishi mumkin)."
      )
      return

    quizzes = generate_quiz_from_text(text)
    await msg.delete()

    for q in quizzes:
      await bot.send_poll(
          chat_id=message.chat.id,
          question=q["question"],
          options=q["options"],
          type="quiz",
          correct_option_id=q["correct_option_id"],
          is_anonymous=False,
      )

    await message.answer(
        "Testlar tayyor! Yana test tuzish uchun yangi PDF yuborishingiz mumkin."
    )
  except Exception as e:
    await message.answer("Test tuzishda xatolik yuz berdi. Qaytadan urinib ko'ring.")
  finally:
    if os.path.exists(file_path):
      os.remove(file_path)
    await state.clear()


async def main():
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
  
