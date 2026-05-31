from datetime import datetime
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from samples.session_srates import Archive_states
from data_base import get_all_user_sessions, delete_session_from_archive


router = Router()


#Команда Архив
@router.message(Command("archive"))
async def cmd_archive(message: Message):
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


#Удаление из архива
@router.message(Archive_states.waiting_for_deletion)
async def process_delete_from_archive(message: Message, state: FSMContext):
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


@router.message(Command("delete_from_archive"))
async def cmd_delete_from_archive(message: Message, state: FSMContext):
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
