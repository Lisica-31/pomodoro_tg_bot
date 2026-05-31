from aiogram.fsm.state import State, StatesGroup

class Session_settings(StatesGroup):
    series_number = State()
    work_time = State()
    relax_time = State() 
    long_relax_time = State()
    save_template = State()
    template_name = State()
    template_name_from_active = State()

class Archive_states(StatesGroup):
    waiting_for_deletion = State()
    waiting_for_template_deletion = State()
    waiting_for_template_run = State()

class Standard_pomodoro_settings(StatesGroup):
    long_relax_time_choice = State()
