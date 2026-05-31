import asyncio
import time

from data_base import save_completed_session


active_session = {}  # {chat_id: {'task': asyncio.Task, 'series': int, 'current': int, 'work_min': int, 'relax_min': int, 'long_relax_min': int, 'user_name': str, 'is_paused': bool, 'pause_start_time': int, 'pause_duration': int, 'current_phase': str, 'phase_start_time': int, 'phase_duration': int}}


#Запуск и отмена сессии
async def start_session(message, state):
    from pomodoro_bot import bot

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
            long_relax_min,
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



#Работа активной сессии + команда Статус
async def run_session(chat_id, user_name, total_series_num, work_minutes, relax_minutes, long_relax_minutes):
    from pomodoro_bot import bot
    
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