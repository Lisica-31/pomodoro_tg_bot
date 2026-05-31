import asyncio
import time
from aiogram.filters import Command
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from samples.session_states import Session_settings, Standard_pomodoro_settings
from services.session_manager import active_session, start_session, run_session


router = Router()


#Настройка кастомной сессиии
@router.message(Command("new_pomodoro"))
async def cmd_new_pomodoro(message: Message, state: FSMContext):
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


@router.message(Session_settings.series_number)
async def setting_serieses(message: Message, state: FSMContext):
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


@router.message(Session_settings.work_time)
async def setting_work_time(message: Message, state: FSMContext):
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


@router.message(Session_settings.relax_time)
async def setting_relax_time(message: Message, state: FSMContext):
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


@router.message(Session_settings.long_relax_time)
async def setting_long_relax_time(message: Message, state: FSMContext):
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


@router.message(Command("standard_pomodoro"))
async def cmd_standard_pomodoro(message: Message, state: FSMContext):
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


@router.callback_query(Standard_pomodoro_settings.long_relax_time_choice)
async def standard_long_relax_time_callback(callback: CallbackQuery, state: FSMContext):
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
