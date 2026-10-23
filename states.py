from aiogram.fsm.state import State, StatesGroup


class DuelStates(StatesGroup):
    """Состояния FSM для мультиплеерных дуэлей."""
    waiting_for_opponent = State()  # Создатель ожидает соперника
    entering_code = State()         # Игрок вводит код лобби
    in_game = State()               # Игрок участвует в матче


class SoloStates(StatesGroup):
    """Состояния FSM для одиночной тренировки."""
    in_game = State()
