import asyncio
import random
from typing import Optional, List, Tuple, Dict
import wikipediaapi
from config import WIKI_USER_AGENT, WIKI_LANGUAGE

# Инициализируем клиент Wikipedia API с обязательным User-Agent
wiki = wikipediaapi.Wikipedia(
    user_agent=WIKI_USER_AGENT,
    language=WIKI_LANGUAGE,
    extract_format=wikipediaapi.ExtractFormat.WIKI
)

# Пространства имен и служебные префиксы, которые не являются статьями
IGNORED_PREFIXES = (
    "категория:", "файл:", "шаблон:", "портал:", "википедия:",
    "обсуждение:", "участник:", "служебная:", "справка:",
    "category:", "file:", "template:", "portal:", "wikipedia:",
    "talk:", "user:", "special:", "help:", "module:", "модуль:"
)

# Запасной список статей на случай сетевых ограничений или отсутствия случайных
FALLBACK_ARTICLES = [
    "Альберт Эйнштейн", "Квантовая механика", "Римская империя",
    "Компьютер", "Интернет", "Эверест", "Кофе", "Шахматы",
    "Франция", "Марс (планета)", "ДНК", "Солнечная система",
    "Аристотель", "Искусственный интеллект", "Пирамида Хеопса",
    "Ренессанс", "Теория относительности", "Музыка", "Океан"
]


def _filter_links(raw_links: Dict[str, wikipediaapi.WikipediaPage]) -> List[str]:
    """Фильтрует внутренние ссылки, исключая категории, шаблоны и файлы."""
    filtered = []
    for link_title in raw_links.keys():
        lower_title = link_title.lower()
        if any(lower_title.startswith(prefix) for prefix in IGNORED_PREFIXES):
            continue
        filtered.append(link_title)
    return sorted(filtered)


def _get_article_sync(title: str) -> Optional[Dict[str, any]]:
    """Синхронно получает информацию о статье: название, выдержка, ссылка, список ссылок."""
    try:
        page = wiki.page(title)
        if not page.exists():
            return None

        # Краткая выдержка (до 300 символов)
        summary = page.summary.strip() if page.summary else "Нет краткого описания."
        if len(summary) > 300:
            summary = summary[:297].rstrip() + "..."

        links = _filter_links(page.links)

        return {
            "title": page.title,
            "summary": summary,
            "url": page.fullurl,
            "links": links,
            "links_count": len(links)
        }
    except Exception as e:
        print(f"Ошибка при получении статьи {title}: {e}")
        return None


async def get_article(title: str) -> Optional[Dict[str, any]]:
    """Асинхронно получает статью из Википедии."""
    return await asyncio.to_thread(_get_article_sync, title)


def _get_random_article_title_sync() -> str:
    """Получает название случайной статьи (с повторными попытками отсева списков/дат)."""
    try:
        # wikipedia-api умеет запрашивать случайные статьи
        random_pages = wiki.random(limit=5)
        for p_title in random_pages:
            p = wiki.page(p_title)
            if p.exists() and len(_filter_links(p.links)) >= 10:
                # Отсеиваем статьи-годы и списки для более интересной игры
                if not ("год" in p_title.lower() or p_title.lower().startswith("список")):
                    return p.title
    except Exception as e:
        print(f"Не удалось получить случайную статью через API: {e}")

    # Fallback на проверенный список
    return random.choice(FALLBACK_ARTICLES)


async def get_duel_pair() -> Tuple[str, str]:
    """
    Генерирует пару статей: старт и финиш (гарантированно разные).
    """
    start = await asyncio.to_thread(_get_random_article_title_sync)
    target = await asyncio.to_thread(_get_random_article_title_sync)

    attempts = 0
    while (start == target or not target) and attempts < 5:
        target = await asyncio.to_thread(_get_random_article_title_sync)
        attempts += 1

    if start == target:
        # Если совпали, берем из запасного списка
        choices = [a for a in FALLBACK_ARTICLES if a != start]
        target = random.choice(choices)

    return start, target


def _is_valid_transition_sync(current_title: str, target_title: str) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, есть ли ссылка на target_title на странице current_title.
    Регистронезависимое сравнение. Возвращает (успех, каноническое имя ссылки).
    """
    try:
        page = wiki.page(current_title)
        if not page.exists():
            return False, None

        links = _filter_links(page.links)
        target_lower = target_title.strip().lower()

        for link in links:
            if link.lower() == target_lower:
                return True, link

        return False, None
    except Exception as e:
        print(f"Ошибка проверки перехода {current_title} -> {target_title}: {e}")
        return False, None


async def is_valid_transition(current_title: str, target_title: str) -> Tuple[bool, Optional[str]]:
    """Асинхронная проверка валидности перехода."""
    return await asyncio.to_thread(_is_valid_transition_sync, current_title, target_title)
