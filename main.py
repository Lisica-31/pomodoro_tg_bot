import asyncio
from pomodoro_bot import dp, bot
from aiogram.types import BotCommand


async def main():
    commands_list = {
        "start": "Начало работы",
        "help": "Справка",
        "standard_pomodoro": "Запуск стандартной сессии Pomodoro",
        "new_pomodoro": "Настройка собственной сессии Pomodoro",
        "pause": "Приостановка текущей сессии",
        "stop": "Приостановка текущей сессии",
        "continue": "Возобновление сессии",
        "status": "Статус текущей сессии",
        "cancel": "Отмена текущую сессию",
        "archive": "Просмотр архива сессий",
        "delete_from_archive": "Удаление сессии из архива",
        "templates": "Просмотр сохраненных шаблонов сессий",
        "save_template": "Сохранение нового шаблона (текущей сессии)",
        "run_template": "Запуск сессии по шаблону",
        "delete_template": "Удаление шаблона",
    }

    commands =[BotCommand(command = command, description = description) for command, description in commands_list.items()]
    await bot.set_my_commands(commands)
    
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())