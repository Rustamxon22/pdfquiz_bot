from aiogram.fsm.state import State, StatesGroup

class QuizState(StatesGroup):
    waiting_pdf = State()
    asking_num_questions = State()
    asking_time = State()
    in_quiz = State()
