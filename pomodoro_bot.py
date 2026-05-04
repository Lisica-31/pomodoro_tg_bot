import asyncio
import time
import sqlite3
from datetime import datetime
from os import getenv
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


from data_base import (
    init_db, save_completed_session , get_all_user_sessions, delete_session_from_archive, 
    save_session_template, get_unique_templates, get_template_by_id, delete_template
)

load_dotenv()
bot_token = getenv ('bot_token')
bot = Bot(token=bot_token)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

init_db()


class Session_settings(StatesGroup):
    series_number = State()
    work_time = State()
    relax_time = State() 
    long_relax_time = State()
    save_template = State()
    template_name = State()
    template_name_from_active = State()  # Для сохранения из активной сессии

class Archive_states(StatesGroup):
    waiting_for_deletion = State()
    waiting_for_template_deletion = State()
    waiting_for_template_run = State()  # Новое состояние для запуска шаблона

class Standard_pomodoro_settings(StatesGroup):
    long_relax_time_choice = State()


active_session = {}  # {chat_id: {'task': asyncio.Task, 'series': int, 'current': int, 'work_min': int, 'relax_min': int, 'long_relax_min': int, 'user_name': str, 'is_paused': bool, 'pause_start_time': int, 'pause_duration': int, 'current_phase': str, 'phase_start_time': int, 'phase_duration': int}}



#Комнада Старт(Хелп)
@dp.message(Command(commands = ["start", "help"]))
async def cmd_start(message: types.Message):
    await message.answer(
        "Метод Pomodoro помогает работать эффективно:\n"
        "• Время работы - фокусируйтесь на задаче\n"
        "• Время отдых - сделайте небольшой перерыв, чтобы перезагрузиться\n"
        "• Длинный отдых после нескольких циклов - восстановите силы!\n\n"

        "Команды:\n"
        "/standard_pomodoro - начать стандартную сессию по методу Pomodoro\n"
        "/new_pomodoro - настроить свою сессию по методу Pomodoro\n"
        "/pause (/stop) - приостановить текущую сессию\n"
        "/continue - возобновить приостановленную сессию\n"
        "/cancel - отменить текущую сессию\n"
        "/status - проверить статус\n\n"

        "/archive - посмотреть архив сессий\n"
        "/delete_from_archive - удалить сессию из архива\n"
        "/templates - посмотреть сохраненные шаблоны\n"
        "/save_template - сохранить текущую сессию как шаблон"
    )



#Настройка кастомной сессиии
@dp.message(Command("new_pomodoro"))
async def cmd_new_pomodoro(message: types.Message, state: FSMContext):
    if message.chat.id in active_session:
        await message.answer("У Вас уже есть активная сессия! Используйте /cancel, чтобы отменить её.")
        return
    
    await message.answer(
        "Настройка метода Помидора\n\n"

        "Сколько циклов работы Вы хотите сделать?\n"
        "(Стандартно - 4 цикла, после которых длинный отдых)\n\n"

        "Введите число от 1 до 10:"
    )
    await state.set_state(Session_settings.series_number)


@dp.message(Session_settings.series_number)
async def setting_serieses(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return
    series = int(message.text)
    if series < 1 or series > 10:
        await message.answer("Количество помидоров должно быть от 1 до 10")
        return
    
    await state.update_data(series = series)
    await message.answer(
        f"Количество циклов: {series}\n\n"

        f"Теперь укажите время работы (в минутах)\n"
        f"(Стандартный цикл - 25 минут)\n\n"

        f"Введите число от 1 до 60:"
    )
    await state.set_state(Session_settings.work_time)


@dp.message(Session_settings.work_time)
async def setting_work_time(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return
    
    work_min = int(message.text)
    if work_min < 1 or work_min > 60:
        await message.answer("Время работы должно быть от 1 до 60 минут")
        return
    
    await state.update_data(work_min = work_min)
    await message.answer(
        f"Время работы: {work_min} минут\n\n"

        f"Теперь укажите время короткого отдыха в минутах\n"
        f"(Стандартный отдых - 5 минут)\n\n"

        f"Введите число от 1 до 30:"
    )
    await state.set_state(Session_settings.relax_time)


@dp.message(Session_settings.relax_time)
async def setting_relax_time(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число (минуты)")
        return
    
    relax_min = int(message.text)
    if relax_min < 1 or relax_min > 30:
        await message.answer("Время отдыха должно быть от 1 до 30 минут")
        return
    await state.update_data(relax_min = relax_min)

    data = await state.get_data()
    serieses = data['series']
    
    if serieses == 1:
        await message.answer(
            f"Продолжительность короткого и длинного отдыха при единственном цикле совпадают"
        )
        await state.update_data(relax_min = relax_min, long_relax_min = relax_min)
        await start_session(message, state)
    else:
        await message.answer(
            f"Время короткого отдыха: {relax_min} минут\n\n"

            f"Теперь укажите время длинного отдыха в минутах\n"
            f"(После {serieses} циклов будет длинный отдых. Стандартный длинный отдых - 15-30 минут)\n\n"

            f"Введите число от 1 до 60:"
        )
        await state.set_state(Session_settings.long_relax_time)


@dp.message(Session_settings.long_relax_time)
async def setting_long_relax_time(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Пожалуйста, введите число.")
        return
    
    long_relax_min = int(message.text)
    if long_relax_min < 1 or long_relax_min > 60:
        await message.answer("Время длинного отдыха должно быть от 1 до 60 минут")
        return
    
    await state.update_data(long_relax_min = long_relax_min)

    await message.answer(
        "Вы хотите сохранить эту сессию как шаблон для будущего использования?\n\n"

        "Да / Нет"
    )
    await state.set_state(Session_settings.save_template)


#Настройка стандартной сессиии
def long_relax_time_keyboard():
    long_relax_time_keyboard = InlineKeyboardMarkup(
        inline_keyboard = [
            [
            InlineKeyboardButton(text = "15 минут", callback_data = "pomodoro_15"),
            InlineKeyboardButton(text = "30 минут", callback_data = "pomodoro_30")
            ]
        ]
    )
    return long_relax_time_keyboard


@dp.message(Command("standard_pomodoro"))
async def cmd_standard_pomodoro(message: types.Message, state: FSMContext):
    if message.chat.id in active_session:
        await message.answer("У Вас уже есть активная сессия! Используйте /cancel, чтобы отменить.")
        return

    await message.answer(
        "Стандартная Pomodoro сессия:\n"
        "• Количество циклов - 4\n"
        "• Время работы - 25 минут\n"
        "• Время короткого отдых - 5 минут\n"
        "• Длинный отдых после нескольких циклов - 15 или 30 минут\n\n"
        
        "Настройте продолжительность длинного отдыха:",
        reply_markup=long_relax_time_keyboard(),
    )
    await state.set_state(Standard_pomodoro_settings.long_relax_time_choice)


@dp.callback_query(Standard_pomodoro_settings.long_relax_time_choice)
async def standard_long_relax_time_callback(callback: types.CallbackQuery, state: FSMContext):
    if callback.message.chat.id in active_session:
        await callback.message.edit_text(
            "У Вас уже есть активная сессия! Используйте /cancel, чтобы отменить.",
            reply_markup=None
        )
        await callback.answer()
        await state.clear()
        return

    if callback.data == "pomodoro_15":
        long_relax_min = 15
    elif callback.data == "pomodoro_30":
        long_relax_min = 30
    else:
        await callback.answer("Неизвестная команда")
        await callback.message.edit_reply_markup(reply_markup = None)
        return

    serieses = 4
    work_min = 25
    relax_min = 5
    phase_duration = work_min * 60

    task = asyncio.create_task(
        run_session(
            callback.message.chat.id,
            callback.from_user.first_name,
            serieses,
            work_min,
            relax_min,
            long_relax_min
        )
    )

    active_session[callback.message.chat.id] = {
        'task': task,
        'session_start_time': time.time(),
        'series': serieses,
        'current': 0,
        'current_phase': 'work',
        'phase_start_time': time.time(),
        'phase_duration': 0,
        'work_time': work_min,
        'relax_time': relax_min,
        'long_relax_time': long_relax_min,
        'user_name': callback.from_user.first_name,      
        'is_paused': False,
        'pause_start_time': 0,
        'pause_duration': 0
    }
        

    await callback.message.edit_text(
        f"Стандартная Pomodoro сессия запущена!\n\n"

        f"Сейчас начнется первый цикл! Удачи и продуктивной работы!\n"
        f"Управление: /pause - пауза, /continue - продолжить, /status - статус, /cancel - отмена, /save_template - сохранить сессию как шаблон.",
        reply_markup = None 
    )

    await state.clear()
    await callback.answer()



#Запуск и отмена сессии
async def start_session(message: types.Message, state: FSMContext):
    data = await state.get_data()
    
    serieses = data['series']
    work_min = data['work_min']
    relax_min = data['relax_min']
    long_relax_min = data.get('long_relax_min', relax_min)
    
    task = asyncio.create_task(
        run_session(
            message.chat.id,
            message.from_user.first_name,
            serieses,
            work_min,
            relax_min,
            long_relax_min
        )
    )
    
    active_session[message.chat.id] = {
        'task': task,
        'session_start_time': time.time(),
        'series': serieses,
        'current': 0,
        'current_phase': 'work',
        'phase_start_time': time.time(),
        'phase_duration': 0,
        'work_time': work_min,
        'relax_time': relax_min,
        'long_relax_time': long_relax_min,
        'user_name': message.from_user.first_name,
        'is_paused': False,
        'pause_start_time': 0,
        'pause_duration': 0
    }
    
    await message.answer(
        f"Сессия работы и отдыха настроена!\n\n"

        f"• Циклов: {serieses}\n"
        f"• Время работы: {work_min} мин.\n"
        f"• Время отдыха: {relax_min} мин.\n"
        f"• Длинный отдых: {long_relax_min} мин.\n\n"

        f"Сейчас начнется первый цикл! Удачи и продуктивной работы!"
        f"Управление: /pause - пауза, /continue - продолжить, /status - статус, /cancel - отмена, /save_template - сохранить сессию как шаблон."
    )
    
    await state.clear()


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in active_session:
        await message.answer("У Вас нет активной сессии.\n\nИспользуйте /standard_pomodoro или /new_pomodoro, чтобы начать.")
        return
    

    if 'task' in active_session[chat_id]:
        active_session[chat_id]['task'].cancel()
        try:
            await active_session[chat_id]['task']
        except asyncio.CancelledError:
            pass
    
    del active_session[chat_id]
    await message.answer("Текущая сессия отменена.")



#Функции для работы паузы (команды Пауза (Стоп) и Продолжить)
def get_phase_elapsed(session):
    if session.get('is_paused', False):
        current_time = session['pause_start_time']
    else:
        current_time = time.time()

    elapsed = current_time - session['phase_start_time'] - session.get('pause_duration', 0)
    return min(max(0, elapsed), session['phase_duration'])


async def waiting_with_pause(chat_id):
    while True:
        if chat_id not in active_session:
            return False
        
        session = active_session[chat_id]

        if session.get('is_paused', False):
            await asyncio.sleep(1)
            continue

        elapsed = get_phase_elapsed(session) 
        if elapsed >= session['phase_duration']:
            return True
        
        await asyncio.sleep(1)


@dp.message(Command(commands=["pause", "stop"]))
async def cmd_pause(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in active_session:
        await message.answer("У Вас нет активной сессии.\n\nИспользуйте /standard_pomodoro или /new_pomodoro, чтобы начать.")
        return

    session = active_session[chat_id]
    if session.get('is_paused', False):
        await message.answer("Сессия уже на паузе. Используйте /continue, чтобы продолжить.")
        return
    
    elapsed = get_phase_elapsed(session) 

    session['is_paused'] = True
    session['pause_start_time'] = time.time()
    session['pause_duration'] = time.time() - session['pause_start_time'] - elapsed

    remaining = session['phase_duration'] - elapsed
    remaining_min = int(remaining // 60)
    remaining_sec = int(remaining % 60)
    phase = "Работа" if session['current_phase'] == 'work' else "Отдых"
    await message.answer(
        f"Сессия приостановлена!\n"
        f"Текущая фаза: {phase}\n"
        f"Осталось времени: {remaining_min} мин. {remaining_sec} сек.\n\n"

        f"Используйсте /continue , чтобы продолжить.\n"
    )


@dp.message(Command("continue"))
async def cmd_continue(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in active_session:
        await message.answer("У Вас нет активной сессии.\n\nИспользуйте /standard_pomodoro или /new_pomodoro, чтобы начать.")
        return

    session = active_session[chat_id]
    if not session.get('is_paused', False):
        await message.answer("Сессия не на паузе. Используйте /pause или /stop, чтобы приостановить.")
        return


    pause_duration = time.time() - session['pause_start_time']
    session['phase_start_time'] += pause_duration
    session['is_paused'] = False

    remaining = session['phase_duration'] - get_phase_elapsed(session)
    remaining_min = int(remaining // 60)
    remaining_sec = int(remaining % 60)
    phase = "Работа" if session['current_phase'] == 'work' else "Отдых"
    await message.answer(
        f"Сессия возобновлена!\n"
        f"Текущая фаза: {phase}\n"
        f"Осталось времени: {remaining_min} мин. {remaining_sec} сек.\n\n"

        f"Удачи!\n"
    )



#Работа активной сессии + команда Статус
async def run_session(chat_id, user_name, total_series_num, work_minutes, relax_minutes, long_relax_minutes):
    completed_series = 0
    session_settings = {
        'series': total_series_num,
        'work_time': work_minutes,
        'relax_time': relax_minutes,
        'long_relax_time': long_relax_minutes
    }
    
    try:
        for series_num in range(1, total_series_num + 1):
            if chat_id not in active_session:
                save_completed_session(chat_id, user_name, session_settings, "cancelled", completed_series)
                return
            
            phase_duration = work_minutes * 60
            if chat_id in active_session:
                active_session[chat_id]['current'] = series_num
                active_session[chat_id]['current_phase'] = 'work'
                active_session[chat_id]['phase_start_time'] = time.time()
                active_session[chat_id]['is_paused'] = False
                active_session[chat_id]['pause_duration'] = 0
                active_session[chat_id]['phase_duration'] = phase_duration

            await bot.send_message(
                chat_id,
                f"Цикл №{series_num} из {total_series_num} начался.\n"
                f"Работа {work_minutes} минут. Сфокусируйтесь!"
            )
            
            success = await waiting_with_pause(chat_id)
            if not success or chat_id not in active_session:
                if chat_id not in active_session:
                    save_completed_session(chat_id, user_name, session_settings, "cancelled", completed_series)
                return


            completed_series = series_num
            if series_num == total_series_num:
                relax_time = long_relax_minutes
                relax_type = "Длинный"
            else:
                relax_time = long_relax_minutes if series_num % 4 == 0 else relax_minutes
                relax_type = "Длинный" if series_num % 4 == 0 else "Короткий"
            
            phase_duration = relax_time * 60
            if chat_id in active_session:
                active_session[chat_id]['current_phase'] = 'relax'
                active_session[chat_id]['phase_start_time'] = time.time()
                active_session[chat_id]['is_paused'] = False
                active_session[chat_id]['pause_duration'] = 0
                active_session[chat_id]['phase_duration'] = phase_duration

            await bot.send_message(
                chat_id,
                f"Работа цикла #{series_num} завершена!\n"
                f"Надо сделать перерыв! {relax_type} отдых {relax_time} минут."
            )
            
            success = await waiting_with_pause(chat_id)
            if not success or chat_id not in active_session:
                if chat_id not in active_session:
                    save_completed_session(chat_id, user_name, session_settings, "cancelled", completed_series)
                return

            if series_num == total_series_num:
                await bot.send_message(
                    chat_id,
                    f"{user_name}! Вы завершили все циклы и длинный отдых!\n"
                    f"Отличная работа!"
                )
                save_completed_session(chat_id, user_name, session_settings, "completed", completed_series)
                break
            else:
                await bot.send_message(
                    chat_id,
                    f"Начинаем следующий цикл!\n"
                    f"Осталось циклов: {total_series_num - series_num}"
                )
        
    except asyncio.CancelledError:
        await bot.send_message(chat_id, f"Сессия отменена, {user_name}!")
        save_completed_session(chat_id, user_name, session_settings, "cancelled", completed_series)
        raise
    finally:
        if chat_id in active_session:
            del active_session[chat_id]


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    chat_id = message.chat.id
    
    if chat_id not in active_session:
        await message.answer("У Вас нет активной сессии.\n\nИспользуйте /standard_pomodoro или /new_pomodoro, чтобы начать.")
        return
    

    session = active_session[chat_id]
    current = session['current']
    total = session['series']
    
    session_time = int(time.time() - session['session_start_time'] - session.get('paused_duration', 0))
    session_hours = session_time // 3600
    session_minutes = (session_time % 3600) // 60
    session_seconds = session_time % 60
    
    phase_elapsed = get_phase_elapsed(session)
    phase_remaining = session['phase_duration'] - phase_elapsed
    if phase_remaining < 0:
        phase_remaining = 0


    if session.get('is_paused', False):
        phase = f"Сессия на паузе! (Этап {'Работа' if session['current_phase'] == 'work' else 'Отдых'})\n"
    else:
        if session['current_phase'] == 'work':
            phase = "Работа"
        else:
            if current % 4 == 0 or current == total:
                phase = "Длинный отдых"
            else:
                phase = "Короткий отдых"
                
    elapsed_min = int(phase_elapsed // 60)
    elapsed_sec = int(phase_elapsed % 60)
    remaining_min = int(phase_remaining // 60)
    remaining_sec = int(phase_remaining % 60)
    await message.answer(
        f"Статус сессии:\n\n"

        f"{'Сессия на паузе!' if session.get('is_paused', False) else 'Активная сессия.'}\n\n"

        f"Прогресс: {current}/{total} циклов\n\n"

        f"Текущая фаза: {phase}\n"
        f"Время в фазе:\n"
        f"Прошло: {elapsed_min} мин. {elapsed_sec} сек.\n"
        f"Осталось: {remaining_min} мин. {remaining_sec} сек.\n\n"

        f"Общее время сессии:\n"
        f"{session_hours} ч. {session_minutes} мин. {session_seconds} сек.\n\n"

        f"Настройки текущей сессии:\n"
        f"Время работы: {session['work_time']} мин.\n"
        f"Время отдыха: {session['relax_time']} мин.\n"
        f"Длинный отдых: {session['long_relax_time']} мин.\n\n"

        f"Управление: /pause - пауза, /continue - продолжить, /status - статус, /cancel - отмена, /save_template - сохранить сессию как шаблон."
    )



#Команда Архив + Удаление из архива
@dp.message(Command("archive"))
async def cmd_archive(message: types.Message):
    sessions = get_all_user_sessions(message.chat.id)
    
    if not sessions:
        await message.answer("У Вас пока нет завершённых сессии.\n\nИспользуйте /standard_pomodoro или /new_pomodoro, чтобы запустить первую!")
        return
    
    response = "Архив Ваших сессий\n\n"
    
    for i, session in enumerate(sessions[:20], 1):
        session_id, status, completion_date, series, work_time, relax_time, long_relax_time, completed_series, total_time = session
        
        status_text = "Завершена" if status == "completed" else "Отменена"
        date_obj = datetime.fromisoformat(completion_date)
        date_str = date_obj.strftime("%d.%m.%Y %H:%M")
        
        response += f"{i}. {status_text} ({date_str})\n"
        response += f"  {completed_series}/{series} циклов. {total_time} мин.\n"
        response += f"  {work_time}/{relax_time}/{long_relax_time} мин.\n"
        response += f"  ID: {session_id}\n\n"
    
    if len(sessions) > 20:
        response += f"\nПоказано 20 из {len(sessions)} сессий. Используйте /delete_from_archive для удаления."
    
    await message.answer(response)


@dp.message(Archive_states.waiting_for_deletion)
async def process_delete_from_archive(message: types.Message, state: FSMContext):
    if message.text.lower() == "/back":
        await message.answer("Удаление отменено.")
        await state.clear()
        return
    
    try:
        session_id = int(message.text)
        deleted = delete_session_from_archive(session_id, message.chat.id)
        
        if deleted:
            await message.answer(f"Сессия с ID {session_id} успешно удалена из архива!")
        else:
            await message.answer(f"Сессия с ID {session_id} не найдена.")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID сессии (число).")
    
    await state.clear()


@dp.message(Command("delete_from_archive"))
async def cmd_delete_from_archive(message: types.Message, state: FSMContext):
    sessions = get_all_user_sessions(message.chat.id)
    
    if not sessions:
        await message.answer("В архиве пусто! Нет сессий для удаления!")
        return
    
    response = "Выберите сессию для удаления:\n\n"
    
    for i, session in enumerate(sessions[:20], 1):
        session_id, status, completion_date, series, work_time, relax_time, long_relax_time, completed_series, total_time = session
        
        date_obj = datetime.fromisoformat(completion_date)
        date_str = date_obj.strftime("%d.%m.%Y %H:%M")
        
        response += f"{i}. ID: {session_id} - {date_str}\n"
        response += f"  {completed_series}/{series} циклов\n\n"
    
    response += "Введите ID сессии, которую хотите удалить или /back для отмены:\n"
    
    await message.answer(response)
    await state.set_state(Archive_states.waiting_for_deletion)



#Команда Шаблоны + Удаление шаблона
@dp.message(Command("templates"))
async def cmd_templates(message: types.Message):
    templates = get_unique_templates(message.chat.id)
    
    if not templates:
        await message.answer("У Вас пока нет сохраненных шаблонов.\n\nИспользуйте /new_pomodoro, чтобы начать, и /save_template, чтобы сохранить первый!")
        return
    
    response = "Ваши шаблоны сессий:\n\n"
    
    for i, template in enumerate(templates, 1):
        series, work_time, relax_time, long_relax_time, template_id, template_name = template
        
        response += f"{i}. {template_name}\n"
        response += f"  {series} циклов. {work_time}/{relax_time}/{long_relax_time} мин.\n"
        response += f"  ID: {template_id}\n\n"
    
    response += "Управление: /run_template <ID> - запустить сессию по ID шаблона\n/delete_template <ID> - удалить шаблон\n"

    await message.answer(response)


@dp.message(Archive_states.waiting_for_template_deletion)
async def process_delete_template(message: types.Message, state: FSMContext):
    if message.text.lower() == "/back":
        await message.answer("Удаление шаблона отменено.")
        await state.clear()
        return
    
    try:
        template_id = int(message.text)
        deleted = delete_template(template_id, message.chat.id)
        
        if deleted:
            await message.answer(f"Шаблон с ID {template_id} успешно удален!")
        else:
            await message.answer(f"Шаблон с ID {template_id} не найден.")
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID шаблона (число).")
    
    await state.clear()


@dp.message(Command("delete_template"))
async def cmd_delete_template(message: types.Message, state: FSMContext):
    templates = get_unique_templates(message.chat.id)
    
    if not templates:
        await message.answer("Нет сохраненных шаблонов для удаления!")
        return
    
    response = "Выберите шаблон для удаления:\n\n"
    
    for i, template in enumerate(templates, 1):
        series, work_time, relax_time, long_relax_time, template_id, template_name = template
        
        response += f"{i}. {template_name}\n"
        response += f"  {series} циклов. {work_time}/{relax_time}/{long_relax_time} мин.\n"
        response += f"  ID: {template_id}\n\n"
    
    response += "Введите ID шаблона, который хотите удалить или /back для отмены:\n"
    
    await message.answer(response)
    await state.set_state(Archive_states.waiting_for_template_deletion)


#Сохрание шаблона
@dp.message(Session_settings.save_template)
async def process_saving_template(message: types.Message, state: FSMContext):
    if message.text.lower() in ["да", "yes", "da"]:
        await message.answer(
            "Введите название для этого шаблона\nили введите /back для отмены сохранения и запуска сессии:"
        )
        await state.set_state(Session_settings.template_name)
    elif message.text.lower() in ["нет", "no", "net"]:
        data = await state.get_data()
        if 'long_relax_min' not in data:
            await state.update_data(long_relax_min = data['relax_min'])
        await start_session(message, state)
    else:
        await message.answer("Пожалуйста, ответьте 'Да' или 'Нет'")


@dp.message(Session_settings.template_name)
async def process_template_name(message: types.Message, state: FSMContext):
    template_name = message.text.strip()
    
    if template_name.lower() == "/back":
        await message.answer("Сохранение шаблона отменено. Запускаем сессию.")
        data = await state.get_data()
        if 'long_relax_min' not in data:
            await state.update_data(long_relax_min = data['relax_min'])
        await start_session(message, state)
        return
    
    if len(template_name) > 50:
        await message.answer("Название слишком длинное (максимум 50 символов)\nПопробуйте снова (или /back для отмены):")
        return
    
    data = await state.get_data()
    
    session_data = {
        'series': data['series'],
        'work_time': data['work_min'],
        'relax_time': data['relax_min'],
        'long_relax_time': data.get('long_relax_min', data['relax_min'])
    }
    
    save_session_template(message.chat.id, template_name, session_data)
    await message.answer(f"Шаблон '{template_name}' сохранен!")
    
    await message.answer("Запускаем сессию.")
    await start_session(message, state)


@dp.message(Command("save_template"))
async def cmd_save_template(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    
    if chat_id not in active_session:
        await message.answer("У Вас нет активной сессии.\n\nИспользуйте /new_pomodoro, чтобы начать.")
        return
    
    session = active_session[chat_id]
    
    await state.update_data(
        series=session['series'],
        work_min=session['work_time'],
        relax_min=session['relax_time'],
        long_relax_min=session['long_relax_time']
    )
    
    await message.answer(
        "Сохранить текущую сессию как шаблон?\n\n"

        f"Настройки сессии:\n"
        f"• Циклов: {session['series']}\n"
        f"• Работа: {session['work_time']} мин.\n"
        f"• Короткий отдых: {session['relax_time']} мин.\n"
        f"• Длинный отдых: {session['long_relax_time']} мин.\n\n"

        f"Введите название для шаблона или /back для отмены:"
    )
    await state.set_state(Session_settings.template_name_from_active)

#(Вспомогательная функция для сохранение шаблона из активной (при остутствии случается конфликт, и уже начатая ранее сессия перезаупускается по-новой))
@dp.message(Session_settings.template_name_from_active)
async def process_saving_template_from_active(message: types.Message, state: FSMContext):
    template_name = message.text.strip()
    
    if template_name.lower() == "/back":
        await message.answer("Сохранение шаблона отменено. Текущая сессия продолжается.")
        await state.clear()
        return
    
    if len(template_name) > 50:
        await message.answer("Название слишком длинное (максимум 50 символов)\n\nПопробуйте снова (или /back для отмены):")
        return
    
    data = await state.get_data()
    
    session_data = {
        'series': data['series'],
        'work_time': data['work_min'],
        'relax_time': data['relax_min'],
        'long_relax_time': data.get('long_relax_min', data['relax_min'])
    }
    
    save_session_template(message.chat.id, template_name, session_data)
    await message.answer(f"Шаблон '{template_name}' из текущей сессии сохранен!\n\nТекущая сессия продолжается.")
    
    await state.clear()


#Запуск сессии по шаблону
@dp.message(Command("run_template"))
async def cmd_run_template(message: types.Message, state: FSMContext):
    chat_id = message.chat.id
    
    if chat_id in active_session:
        await message.answer("У Вас уже есть активная сессия! Используйте /cancel, чтобы отменить её.")
        return
    
    parts = message.text.split(maxsplit = 1)
    if len(parts) < 2:
        await message.answer(
            "Пожалуйста, укажите ID шаблона.\n\nПосмотреть ID шаблонов можно через /templates"
        )
        return
    
    try:
        template_id = int(parts[1])
    except ValueError:
        await message.answer("ID шаблона должен быть числом!")
        return
    

    connection = sqlite3.connect('pomodoro_sessions.db')
    cursor = connection.cursor()
    
    cursor.execute('''
        SELECT series, work_time, relax_time, long_relax_time, template_name
        FROM session_templates
        WHERE id = ? AND chat_id = ?
        ORDER BY id DESC
        LIMIT 1
    ''', (template_id, chat_id))
    
    template_settings = cursor.fetchone()
    connection.close()
    
    if not template_settings:
        await message.answer(f"Шаблон с ID {template_id} не найден.\n\nПосмотреть ID шаблонов можно через /templates")
        return
    
    serieses, work_min, relax_min, long_relax_min, template_name = template_settings
    

    task = asyncio.create_task(
        run_session(
            chat_id,
            message.from_user.first_name,
            serieses,
            work_min,
            relax_min,
            long_relax_min
        )
    )
    
    active_session[chat_id] = {
        'task': task,
        'session_start_time': time.time(),
        'series': serieses,
        'current': 0,
        'current_phase': 'work',
        'phase_start_time': time.time(),
        'phase_duration': 0,
        'work_time': work_min,
        'relax_time': relax_min,
        'long_relax_time': long_relax_min,
        'user_name': message.from_user.first_name,
        'is_paused': False,
        'pause_start_time': 0,
        'pause_duration': 0
    }
    
    await message.answer(
        f"Сессия по шаблону '{template_name}' запущена!\n\n"

        f"Настройки текущей сессии:\n"
        f"• Циклов: {serieses}\n"
        f"• Время работы: {work_min} мин.\n"
        f"• Короткий отдых: {relax_min} мин.\n"
        f"• Длинный отдых: {long_relax_min} мин.\n\n"

        f"Сейчас начнется первый цикл! Удачи и продуктивной работы!"
        f"Управление: /pause - пауза, /continue - продолжить, /status - статус, /cancel - отмена."
    )
