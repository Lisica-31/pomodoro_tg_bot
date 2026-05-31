import asyncio
import time
import sqlite3
from aiogram.filters import Command
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from samples.session_states import Session_settings, Archive_states
from services.session_manager import active_session, start_session, run_session
from data_base import save_session_template, get_unique_templates, get_template_by_id, delete_template


router = Router()


#Команда шаблоны
@router.message(Command("templates"))
async def cmd_templates(message: Message):
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


#Удаление шаблона
@router.message(Archive_states.waiting_for_template_deletion)
async def process_delete_template(message: Message, state: FSMContext):
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


@router.message(Command("delete_template"))
async def cmd_delete_template(message: Message, state: FSMContext):
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
@router.message(Session_settings.save_template)
async def process_saving_template(message: Message, state: FSMContext):
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


@router.message(Session_settings.template_name)
async def process_template_name(message: Message, state: FSMContext):
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


@router.message(Command("save_template"))
async def cmd_save_template(message: Message, state: FSMContext):
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
@router.message(Session_settings.template_name_from_active)
async def process_saving_template_from_active(message: Message, state: FSMContext):
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
@router.message(Command("run_template"))
async def cmd_run_template(message: Message, state: FSMContext):
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
