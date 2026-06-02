"""Каталог звуков по умолчанию (ключи, emoji, подписи из ТЗ и макетов)."""

DEFAULT_SOUNDS = [
    # Помодоро — звук завершения таймера
    {"key": "bell", "category": "timer_end", "title": "Колокольчик", "emoji": "🔔", "sort_order": 1},
    {"key": "chime", "category": "timer_end", "title": "Перезвон", "emoji": "🎵", "sort_order": 2},
    {"key": "success", "category": "timer_end", "title": "Успех", "emoji": "✅", "sort_order": 3},
    {"key": "ding", "category": "timer_end", "title": "Динь", "emoji": "🔊", "sort_order": 4},
    {"key": "soft", "category": "timer_end", "title": "Мягкий", "emoji": "🎶", "sort_order": 5},
    {"key": "none", "category": "timer_end", "title": "Без звука", "emoji": "🔇", "sort_order": 99},
    {"key": "default", "category": "timer_end", "title": "По умолчанию", "emoji": "🔔", "sort_order": 0},
    # Помодоро — фоновый звук
    {"key": "none", "category": "work_background", "title": "Без звука", "emoji": "🔇", "sort_order": 99},
    {"key": "rain", "category": "work_background", "title": "Дождь", "emoji": "🌧️", "sort_order": 1},
    {"key": "forest", "category": "work_background", "title": "Лес", "emoji": "🌲", "sort_order": 2},
    {"key": "coffee", "category": "work_background", "title": "Кафе", "emoji": "☕", "sort_order": 3},
    {"key": "wind", "category": "work_background", "title": "Ветер", "emoji": "💨", "sort_order": 4},
    # Настройки — уведомление по задаче
    {"key": "default", "category": "notification", "title": "По умолчанию", "emoji": "🔔", "sort_order": 0},
    {"key": "gentle", "category": "notification", "title": "Мягкий", "emoji": "🎵", "sort_order": 1},
    {"key": "alert", "category": "notification", "title": "Напоминание", "emoji": "⏰", "sort_order": 2},
    {"key": "none", "category": "notification", "title": "Без звука", "emoji": "🔇", "sort_order": 99},
    # Настройки — завершение задачи
    {"key": "default", "category": "completion", "title": "По умолчанию", "emoji": "✅", "sort_order": 0},
    {"key": "chime", "category": "completion", "title": "Перезвон", "emoji": "🎵", "sort_order": 1},
    {"key": "pop", "category": "completion", "title": "Щелчок", "emoji": "🔊", "sort_order": 2},
    {"key": "none", "category": "completion", "title": "Без звука", "emoji": "🔇", "sort_order": 99},
]

SOUND_CATEGORY_CHOICES = [
    ("timer_end", "Звук завершения таймера"),
    ("work_background", "Фоновый звук помодоро"),
    ("notification", "Звук уведомления"),
    ("completion", "Звук завершения задачи"),
]
