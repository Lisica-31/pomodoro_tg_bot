import asyncio
import time
from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message

from services.session_manager import active_session, get_phase_elapsed
from data_base import save_completed_session


router = Router()

#Команда отменить сессию
@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
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


#Команды пауза и продолжить
@router.message(Command(commands=["pause", "stop"]))
async def cmd_pause(message: Message):
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


@router.message(Command("continue"))
async def cmd_continue(message: Message):
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


#Команда статус
@router.message(Command("status"))
async def cmd_status(message: Message):
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

