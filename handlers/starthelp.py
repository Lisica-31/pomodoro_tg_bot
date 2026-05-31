from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message


router = Router()


#Комнада Старт(Хелп)
@router.message(Command(commands = ["start", "help"]))
async def cmd_start(message: Message):
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
