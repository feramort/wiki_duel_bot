import asyncio
import html
import logging
import os
import random
from typing import List

from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

import config
import database as db
from states import DuelStates, SoloStates
import wiki_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# --- Клавиатуры ---

def get_main_menu():
    """Главное меню бота."""
    kb = [
        [KeyboardButton(text="⚔️ Создать дуэль"), KeyboardButton(text="🔑 Присоединиться")],
        [KeyboardButton(text="🕹 Одиночная игра"), KeyboardButton(text="📊 Моя статистика")],
        [KeyboardButton(text="🏆 Топ игроков"), KeyboardButton(text="📖 Правила игры")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def build_article_keyboard(links: List[str], offset: int = 0, is_solo: bool = False) -> InlineKeyboardMarkup:
    """Генерирует инлайн-кнопки со ссылками на странице с пагинацией."""
    PAGE_SIZE = 6
    total_links = len(links)
    current_slice = links[offset:offset + PAGE_SIZE]

    buttons = []
    # Добавляем ссылки по 2 в ряд
    for i in range(0, len(current_slice), 2):
        row = []
        for j in range(2):
            if i + j < len(current_slice):
                idx = offset + i + j
                title = current_slice[i + j]
                display_title = title if len(title) <= 24 else title[:22] + ".."
                row.append(InlineKeyboardButton(text=f"🔗 {display_title}", callback_data=f"go:{idx}"))
        buttons.append(row)

    # Кнопки навигации по страницам ссылок
    nav_row = []
    if offset > 0:
        prev_offset = max(0, offset - PAGE_SIZE)
        nav_row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"page:{prev_offset}"))
    if offset + PAGE_SIZE < total_links:
        next_offset = offset + PAGE_SIZE
        nav_row.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"page:{next_offset}"))
    if nav_row:
        buttons.append(nav_row)

    # Кнопка сдачи
    surrender_cb = "solo_surrender" if is_solo else "duel_surrender"
    buttons.append([InlineKeyboardButton(text="🏳️ Сдаться", callback_data=surrender_cb)])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def send_article_view(chat_id: int, state: FSMContext, current_title: str, target_title: str, steps: int, is_solo: bool = False):
    """Отправляет игроку карточку текущей статьи и доступные ссылки."""
    article = await wiki_service.get_article(current_title)
    if not article:
        await bot.send_message(chat_id, f"⚠️ Не удалось загрузить статью «{current_title}». Попробуйте сделать переход еще раз.")
        return

    # Сохраняем актуальный список ссылок в FSM для безопасной адресации по индексам
    links = article["links"]
    await state.update_data(
        current_title=article["title"],
        target_title=target_title,
        links=links,
        steps=steps,
        offset=0
    )

    clean_summary = html.escape(article['summary'])
    clean_target = html.escape(target_title)
    clean_curr = html.escape(article['title'])

    text = (
        f"🎯 <b>Цель:</b> <u>{clean_target}</u>\n"
        f"📍 <b>Текущая статья:</b> <b>{clean_curr}</b>\n"
        f"👣 <b>Сделано переходов:</b> {steps}\n\n"
        f"📝 <i>{clean_summary}</i>\n\n"
        f"🌐 <a href='{article['url']}'>Открыть статью в Википедии</a>\n\n"
        f"👇 <i>Выберите ссылку кнопкой или отправьте ее точное название сообщением:</i>"
    )

    keyboard = build_article_keyboard(links, offset=0, is_solo=is_solo)
    await bot.send_message(chat_id, text, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)


# --- Обработчики команд ---

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user = message.from_user
    logger.info(f"Получена команда /start от пользователя {user.full_name} (id={user.id})")
    await state.clear()
    db.get_or_create_user(user.id, user.username, user.first_name)

    user_name = html.escape(user.first_name or "игрок")
    welcome_text = (
        f"Привет, <b>{user_name}</b>! 👋\n\n"
        "Добро пожаловать в <b>Wiki Duel Bot</b> — игру-гонку по Википедии!\n\n"
        "🎮 <b>Правила просты:</b>\n"
        "Вам и сопернику дается стартовая и финишная статья. "
        "Побеждает тот, кто первым доберется до цели, переходя исключительно "
        "по ссылкам внутри статей!\n\n"
        "Выберите действие в меню ниже 👇"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(), parse_mode="HTML")


@dp.message(F.text == "📖 Правила игры")
async def cmd_rules(message: types.Message):
    rules = (
        "📖 <b>Правила игры «Вики-Дуэль»:</b>\n\n"
        "1. В начале раунда генерируются две случайные статьи: <b>Старт</b> и <b>Финиш</b>.\n"
        "2. Вы начинаете со стартовой статьи и должны добраться до финишной.\n"
        "3. Перемещаться можно <b>только</b> по тем ссылкам, которые физически есть на текущей странице.\n"
        "4. Вы можете нажимать на предложенные инлайн-кнопки или вручную писать боту название статьи из текста.\n"
        "5. В режиме дуэли побеждает тот, кто первым перейдет на целевую статью!\n\n"
        "Удачи в путешествии по глубинам знаний! 🚀"
    )
    await message.answer(rules, parse_mode="HTML")


@dp.message(F.text == "📊 Моя статистика")
async def cmd_stats(message: types.Message):
    stats = db.get_user_stats(message.from_user.id)
    if not stats:
        await message.answer("Статистика пока пуста. Сыграйте первую дуэль!")
        return

    wins = stats["wins"]
    losses = stats["losses"]
    total = stats["total_games"]
    winrate = round((wins / total * 100), 1) if total > 0 else 0

    text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"🏆 Побед: <b>{wins}</b>\n"
        f"❌ Поражений: <b>{losses}</b>\n"
        f"🎮 Всего матчей: <b>{total}</b>\n"
        f"📈 Процент побед: <b>{winrate}%</b>"
    )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text == "🏆 Топ игроков")
async def cmd_top(message: types.Message):
    top = db.get_top_players(10)
    if not top:
        await message.answer("В таблице лидеров пока никого нет. Станьте первым!")
        return

    text = "🏆 <b>Топ-10 игроков Вики-Дуэлей:</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, player in enumerate(top, 1):
        icon = medals[i - 1] if i <= 3 else f"{i}."
        raw_name = player["first_name"] or player["username"] or f"Игрок {player['user_id']}"
        name = html.escape(raw_name)
        text += f"{icon} <b>{name}</b> — 🏆 {player['wins']} побед (всего игр: {player['total_games']})\n"

    await message.answer(text, parse_mode="HTML")


# --- Создание и подключение к дуэли ---

@dp.message(F.text == "⚔️ Создать дуэль")
async def create_duel(message: types.Message, state: FSMContext):
    await state.clear()
    msg = await message.answer("⏳ Подбираем интересные статьи для дуэли...")

    start_art, target_art = await wiki_service.get_duel_pair()
    code = str(random.randint(100000, 999999))

    match = db.create_match(code, message.from_user.id, start_art, target_art)
    await state.set_state(DuelStates.waiting_for_opponent)
    await state.update_data(match_id=match["id"], code=code)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить лобби", callback_data="cancel_lobby")]
    ])

    await msg.edit_text(
        f"⚔️ <b>Лобби дуэли создано!</b>\n\n"
        f"🔑 Код подключения: <code>{code}</code>\n\n"
        f"🏁 <b>Старт:</b> {html.escape(start_art)}\n"
        f"🎯 <b>Цель:</b> {html.escape(target_art)}\n\n"
        f"Отправьте этот код вашему сопернику. Игра начнется автоматически, как только он подключится!",
        reply_markup=kb,
        parse_mode="HTML"
    )


@dp.callback_query(F.data == "cancel_lobby", DuelStates.waiting_for_opponent)
async def cancel_lobby_cb(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    match_id = data.get("match_id")
    if match_id:
        db.cancel_match(match_id)
    await state.clear()
    await callback.message.edit_text("❌ Лобби отменено.")
    await callback.answer()


@dp.message(F.text == "🔑 Присоединиться")
async def join_duel_prompt(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(DuelStates.entering_code)
    await message.answer(
        "🔑 Введите 6-значный код комнаты, полученный от соперника:\n"
        "(или отправьте /cancel для отмены)",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_main_menu())


@dp.message(DuelStates.entering_code)
async def process_join_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    match = db.get_match_by_code(code)

    if not match:
        await message.answer("❌ Комната с таким кодом не найдена. Проверьте код и попробуйте снова:")
        return

    if match["status"] != "waiting":
        await message.answer("⚠️ Эта дуэль уже началась или была завершена.", reply_markup=get_main_menu())
        await state.clear()
        return

    if match["creator_id"] == message.from_user.id:
        await message.answer("Вы не можете присоединиться к собственной дуэли! Ожидайте второго игрока.")
        return

    # Подключаем игрока
    updated_match = db.join_match(code, message.from_user.id)
    match_id = updated_match["id"]
    creator_id = updated_match["creator_id"]
    opponent_id = message.from_user.id
    start_art = updated_match["start_article"]
    target_art = updated_match["target_article"]

    # Инициализируем состояние подключившегося
    await state.set_state(DuelStates.in_game)
    await state.update_data(match_id=match_id)

    # Инициализируем состояние создателя
    creator_state = FSMContext(
        storage=storage,
        key=types.StorageKey(bot_id=bot.id, chat_id=creator_id, user_id=creator_id)
    )
    await creator_state.set_state(DuelStates.in_game)
    await creator_state.update_data(match_id=match_id)

    # Уведомляем создателя
    await bot.send_message(
        creator_id,
        f"⚡ <b>Соперник подключился! Дуэль началась!</b>\n"
        f"🏁 Старт: <b>{html.escape(start_art)}</b> ➡️ 🎯 Финиш: <b>{html.escape(target_art)}</b>",
        parse_mode="HTML"
    )
    await send_article_view(creator_id, creator_state, start_art, target_art, steps=0)

    # Уведомляем второго игрока
    await message.answer(
        f"⚡ <b>Вы успешно подключились к дуэли!</b>\n"
        f"🏁 Старт: <b>{html.escape(start_art)}</b> ➡️ 🎯 Финиш: <b>{html.escape(target_art)}</b>",
        parse_mode="HTML"
    )
    await send_article_view(opponent_id, state, start_art, target_art, steps=0)


# --- Одиночный режим ---

@dp.message(F.text == "🕹 Одиночная игра")
async def start_solo_game(message: types.Message, state: FSMContext):
    await state.clear()
    msg = await message.answer("⏳ Генерируем маршрут для тренировки...")
    start_art, target_art = await wiki_service.get_duel_pair()

    await state.set_state(SoloStates.in_game)
    await msg.edit_text(
        f"🕹 <b>Одиночный режим</b>\n\n"
        f"🏁 Старт: <b>{html.escape(start_art)}</b>\n"
        f"🎯 Финиш: <b>{html.escape(target_art)}</b>\n\n"
        f"Попробуйте дойти до цели за минимальное количество шагов!",
        parse_mode="HTML"
    )
    await send_article_view(message.chat.id, state, start_art, target_art, steps=0, is_solo=True)


# --- Игровая логика: Пагинация ссылок и выбор кнопок ---

@dp.callback_query(F.data.startswith("page:"))
async def handle_pagination(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    links = data.get("links", [])
    offset = int(callback.data.split(":")[1])
    is_solo = (await state.get_state()) == SoloStates.in_game.state

    await state.update_data(offset=offset)
    keyboard = build_article_keyboard(links, offset=offset, is_solo=is_solo)
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@dp.callback_query(F.data.startswith("go:"))
async def handle_link_click(callback: types.CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    links = data.get("links", [])

    if idx >= len(links):
        await callback.answer("Ссылка устарела.", show_alert=True)
        return

    selected_article = links[idx]
    await callback.answer(f"Переход к: {selected_article}")
    await process_step(callback.from_user.id, callback.message.chat.id, selected_article, state)


@dp.message(DuelStates.in_game)
@dp.message(SoloStates.in_game)
async def handle_text_step(message: types.Message, state: FSMContext):
    candidate = message.text.strip()
    data = await state.get_data()
    current_title = data.get("current_title")

    # Проверяем, есть ли ссылка на указанную статью
    is_valid, canonical_name = await wiki_service.is_valid_transition(current_title, candidate)
    if not is_valid:
        await message.reply(
            f"❌ В статье <b>«{html.escape(current_title)}»</b> нет ссылки на <b>«{html.escape(candidate)}»</b>.\n\n"
            "Воспользуйтесь инлайн-кнопками или введите точное название ссылки из статьи.",
            parse_mode="HTML"
        )
        return

    await process_step(message.from_user.id, message.chat.id, canonical_name, state)


async def process_step(user_id: int, chat_id: int, next_article: str, state: FSMContext):
    """Общий обработчик перехода на следующую статью."""
    current_state = await state.get_state()
    is_solo = (current_state == SoloStates.in_game.state)
    data = await state.get_data()
    target_title = data.get("target_title")
    steps = data.get("steps", 0) + 1

    # Проверка победы
    if next_article.strip().lower() == target_title.strip().lower():
        if is_solo:
            await bot.send_message(
                chat_id,
                f"🎉 <b>Поздравляем! Вы достигли цели!</b>\n\n"
                f"🎯 Финишная статья: <b>{html.escape(target_title)}</b>\n"
                f"👣 Пройдено за шагов: <b>{steps}</b>",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
            await state.clear()
            return
        else:
            # Дуэль завершена
            match_id = data.get("match_id")
            updated_match = db.finish_match(match_id, winner_id=user_id)
            creator_id = updated_match["creator_id"]
            opponent_id = updated_match["opponent_id"]
            loser_id = opponent_id if user_id == creator_id else creator_id

            # Оповещаем победителя
            await bot.send_message(
                user_id,
                f"🏆 <b>ПОБЕДА! ВЫ ВЫИГРАЛИ ДУЭЛЬ!</b> 🏆\n\n"
                f"Вы первым добрались до цели <b>{html.escape(target_title)}</b> за <b>{steps}</b> шагов!",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )

            # Оповещаем проигравшего
            loser_state = FSMContext(
                storage=storage,
                key=types.StorageKey(bot_id=bot.id, chat_id=loser_id, user_id=loser_id)
            )
            await loser_state.clear()
            await bot.send_message(
                loser_id,
                f"🏁 <b>Дуэль завершена!</b>\n\n"
                f"Соперник первым добрался до цели <b>{html.escape(target_title)}</b>.\n"
                f"Не расстраивайтесь, повезет в следующем раунде!",
                reply_markup=get_main_menu(),
                parse_mode="HTML"
            )
            await state.clear()
            return

    # Если дуэль не окончена — обновляем базу (для мультиплеера)
    if not is_solo:
        match_id = data.get("match_id")
        db.update_player_step(match_id, user_id, next_article)

    # Отображаем новую статью
    await send_article_view(chat_id, state, next_article, target_title, steps=steps, is_solo=is_solo)


# --- Сдача в игре ---

@dp.callback_query(F.data == "solo_surrender", SoloStates.in_game)
async def solo_surrender(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🏳️ Игра завершена (вы сдались).")
    await bot.send_message(callback.from_user.id, "Главное меню:", reply_markup=get_main_menu())
    await callback.answer()


@dp.callback_query(F.data == "duel_surrender", DuelStates.in_game)
async def duel_surrender(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    match_id = data.get("match_id")
    user_id = callback.from_user.id

    match = db.get_match_by_id(match_id)
    if not match or match["status"] != "in_progress":
        await callback.answer("Дуэль уже завершена.", show_alert=True)
        return

    creator_id = match["creator_id"]
    opponent_id = match["opponent_id"]
    winner_id = opponent_id if user_id == creator_id else creator_id

    db.finish_match(match_id, winner_id=winner_id)

    # Сдавшийся
    await state.clear()
    await callback.message.edit_text("🏳️ Вы сдались. Поражение засчитано.")
    await bot.send_message(user_id, "Главное меню:", reply_markup=get_main_menu())

    # Победитель
    winner_state = FSMContext(
        storage=storage,
        key=types.StorageKey(bot_id=bot.id, chat_id=winner_id, user_id=winner_id)
    )
    await winner_state.clear()
    await bot.send_message(
        winner_id,
        "🏆 <b>Соперник сдался! Вам присуждена победа!</b>",
        reply_markup=get_main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# --- Render Health Check ---

async def start_render_health_server():
    """Запускает мини-сервер для health check от Render (для бесплатного тарифа Web Service)."""
    port_str = os.getenv("PORT")
    if not port_str:
        return  # Запущен локально на ПК, порт не требуется

    try:
        port = int(port_str)
        app = web.Application()

        async def health(request):
            return web.Response(text="Wiki Duel Bot is alive! 🚀")

        app.router.add_get("/", health)
        app.router.add_get("/health", health)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Render health check сервер успешно запущен на порту {port}")
    except Exception as e:
        logger.error(f"Не удалось запустить health-check сервер: {e}")


# --- Точка входа ---

async def main():
    logger.info("Инициализация базы данных...")
    db.init_db()

    # Если бот развернут на Render, запускаем пинг-сервер
    await start_render_health_server()

    if not config.BOT_TOKEN or config.BOT_TOKEN == "your_telegram_bot_token_here":
        print("\n" + "=" * 60)
        print("ОШИБКА: Задайте токен бота в файле .env (BOT_TOKEN=...)!")
        print("Получить токен можно у @BotFather в Telegram.")
        print("=" * 60 + "\n")
        return

    logger.info("Удаление старых вебхуков...")
    await bot.delete_webhook(drop_pending_updates=False)

    logger.info("Запуск бота Wiki Duel в режиме Polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
