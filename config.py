import os


def _read_boolean_env(name, default):
    """Читает булево значение из окружения с безопасным fallback."""

    value = os.getenv(name)

    # Без переменной окружения используем локальное значение по умолчанию.
    if value is None:
        return default

    normalized_value = value.strip().casefold()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    # Неизвестное значение не должно случайно включать реальные публикации.
    return default


# За сколько последних дней будем брать новости.
# Пока значение просто храним в конфигурации.
# Сам фильтр по дате добавим отдельным этапом.
NEWS_LOOKBACK_DAYS = 3


# Максимальное количество новостей,
# которое будем обрабатывать за один запуск.
MAX_NEWS_PER_RUN = 1


# Тестовый режим для безопасной разработки.
#
# При True программа полностью обрабатывает и показывает новости,
# но не отправляет посты и не меняет storage/published.json.
#
# Локально безопасный режим включён всегда. GitHub Actions явно передаёт
# LIVECRIME_DRY_RUN=false только для ручного рабочего запуска.
DRY_RUN = _read_boolean_env("LIVECRIME_DRY_RUN", default=True)


# Основной режим публикации:
# каждая выбранная новость отправляется отдельным постом.
POST_MODE = "single"


# Только эти сигналы самостоятельно допускают материал в hard true crime.
# Формы "убил" и "убит" нужны отдельно от существительного "убийство".
STRONG_TOPICS = [
    "убий",
    "убил",
    "убит",
    "изнасил",
    "расстрел",
    "застрел",
    "самоубий",
    "суицид",
    "покончил с собой",
    "покончила с собой",
]


# Эти действия становятся serious только вместе с тяжёлым исходом.
CONDITIONAL_SERIOUS_TOPICS = [
    "покушен",
    "нападен",
    "стрельб",
    "избил",
    "избиен",
]


# Все остальные crime-слова используются лишь как контекст.
# Их количество и score никогда не заменяют hard serious whitelist.
CONTEXTUAL_TOPICS = [
    "покушен",
    "ограб",
    "похищ",
    "мошеннич",
    "избил",
    "избиен",
    "нападен",
    "стрельб",
    "вооруж",
    "краж",
    "наркот",
    "задерж",
    "арест",
    "уголовн",
    "преступ",
    "подозрев",
    "следств",
    "полици",
    "обвин",
    "розыск",
    "разыск",
    "приговор",
    "осужден",
    "осуждён",
    "пропал",
    "пропав",
    "обнаружен труп",
    "обнаружили тело",
    "нашли тело",
]


# Общий список сохраняет единый порядок matched_topics и хэштегов.
TOPICS = STRONG_TOPICS + [
    topic for topic in CONTEXTUAL_TOPICS
    if topic not in STRONG_TOPICS
]


# Слабая процедурная новость не должна публиковаться только ради частоты.
MIN_PUBLICATION_SCORE = 4


# Каждая тематическая основа получает короткий Telegram-хэштег.
# Несколько форм одного смысла могут вести к одному тегу.
TOPIC_TAGS = {
    "убий": "#убийство",
    "убил": "#убийство",
    "убит": "#убийство",
    "покушен": "#покушение",
    "ограб": "#ограбление",
    "похищ": "#похищение",
    "мошеннич": "#мошенничество",
    "задерж": "#задержание",
    "арест": "#арест",
    "нападен": "#нападение",
    "изнасил": "#изнасилование",
    "расстрел": "#стрельба",
    "застрел": "#стрельба",
    "стрельб": "#стрельба",
    "уголовн": "#уголовноедело",
    "преступ": "#преступление",
    "следств": "#расследование",
    "полици": "#полиция",
    "обвин": "#обвинение",
    "подозрев": "#подозреваемый",
    "розыск": "#розыск",
    "разыск": "#розыск",
    "судебн": "#суд",
    "суд": "#суд",
    "приговор": "#приговор",
    "осужден": "#приговор",
    "осуждён": "#приговор",
    "пропал": "#розыск",
    "пропав": "#розыск",
    "обнаружен труп": "#происшествие",
    "обнаружили тело": "#происшествие",
    "нашли тело": "#происшествие",
    "избил": "#избиение",
    "избиен": "#избиение",
    "самоубий": "#суицид",
    "суицид": "#суицид",
    "покончил с собой": "#суицид",
    "покончила с собой": "#суицид",
}


# Список источников новостей.
#
# RSS и HTML приводятся collectors к одному формату news_item.
# В дальнейшем сюда же можно добавить источники типа "api".


SOURCES = [
    {
        "name": "Lenta.ru",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://lenta.ru/rss/news",
    },

    {
        "name": "SarBC: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://www.sarbc.ru/rss/data-utf/event.rss",
    },

    # Москва
    {
        "name": "АГН Москва: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://www.mskagency.ru/rss/incident.rss",
    },

    # Москва + Московская область
    {
        "name": "StolicaMedia: происшествия Москвы и области",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://stolicamedia.ru/export/new/newsByRubric_121_188.rss",
    },

    # Санкт-Петербург
    {
        "name": "PeterburgMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://peterburgmedia.ru/export/new/newsByRubric_88_198.rss",
    },

    # Краснодарский край
    {
        "name": "KrasnodarMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://krasnodarmedia.su/export/new/newsByRubric_25_79.rss",
    },

    # Сибирь: Иркутская область
    {
        "name": "IrkutskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://irkutskmedia.ru/export/new/newsByRubric_14_51.rss",
    },

    # Сибирь: Красноярский край
    {
        "name": "KrasnoyarskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://krasnoyarskmedia.ru/export/new/newsByRubric_26_16.rss",
    },

    # Сибирь: Омская область
    {
        "name": "OmskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://omskmedia.su/export/new/newsByRubric_38_181.rss",
    },

    # Дальний Восток: Приморский край
    {
        "name": "PrimaMedia: происшествия Приморья",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://primamedia.ru/export/new/newsByRubric_43_19.rss",
    },

    # Дальний Восток: Хабаровский край
    {
        "name": "AmurMedia: происшествия Хабаровского края",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://amurmedia.ru/export/new/newsByRubric_77_27.rss",
    },

    # Дальний Восток: Сахалин
    {
        "name": "SakhalinMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://sakhalinmedia.ru/export/new/newsByRubric_64_40.rss",
    },

    # Дальний Восток: Якутия
    {
        "name": "YakutiaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://yakutiamedia.ru/export/new/newsByRubric_55_71.rss",
    },

    # Дальний Восток: Амурская область
    {
        "name": "PriamurMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://priamurmedia.ru/export/new/newsByRubric_2_121.rss",
    },

    # Дальний Восток: Камчатка
    {
        "name": "KamchatkaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://kamchatkamedia.ru/export/new/newsByRubric_18_118.rss",
    },

    # Дальний Восток: Еврейская автономная область
    {
        "name": "EAOMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://eaomedia.ru/export/new/newsByRubric_11_35.rss",
    },

    # Дальний Восток: Магаданская область
    {
        "name": "MagadanMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://magadanmedia.ru/export/new/newsByRubric_31_63.rss",
    },

    # Дальний Восток: Чукотка
    {
        "name": "ChukotkaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": True,
        "url": "https://chukotkamedia.ru/export/new/newsByRubric_83_44.rss",
    },

    # HTML-источники используют отдельные адаптеры.
    # Полный текст статьи по-прежнему загружается позже через article/fetcher.py.
    {
        "name": "116.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://116.ru/text/incidents/",
        "adapter": "116ru",
        "timezone": "Europe/Moscow",
        "limit": 40,
    },
    {
        "name": "E1.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://www.e1.ru/text/incidents/",
        "adapter": "e1ru",
        "timezone": "Asia/Yekaterinburg",
        "limit": 40,
    },
    {
        "name": "VN.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://vn.ru/news/proisshestviya/",
        "adapter": "vnru",
        "timezone": "Asia/Novosibirsk",
        "limit": 40,
    },
    {
        "name": "vtomske.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://vtomske.ru/tag/incident",
        "adapter": "vtomske",
        "timezone": "Asia/Tomsk",
        "limit": 40,
    },
    {
        "name": "Amic.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://www.amic.ru/news/incident",
        "adapter": "amic",
        "timezone": "Asia/Barnaul",
        "limit": 40,
    },
    {
        "name": "A42: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": True,
        "url": "https://gazeta.a42.ru/lenta/news/kuzbass/proisshestviya",
        "adapter": "a42",
        "timezone": "Asia/Novokuznetsk",
        "limit": 40,
    },
]

# Слова и выражения, при которых новость
# скорее всего не относится к нужной криминальной тематике.
EXCLUDE_KEYWORDS = [
    "спорт",
    "бокс",
    "футбол",
    "хоккей",
    "игра",
    "фильм",
    "сериал",
    "книга",
    "рецензия",
]

# Покушение, нападение, стрельба или избиение проходят только тогда,
# когда рядом явно указан смертельный или угрожающий жизни исход.
SERIOUS_OUTCOME_KEYWORDS = [
    "до смерти",
    "гибел",
    "погиб",
    "скончал",
    "смерт",
    "тяжкий вред",
    "тяжёлый вред",
    "тяжелый вред",
    "угроза жизни",
    "угрозой жизни",
    "несколько жертв",
    "множественные жертвы",
    "тяжело ранен",
    "тяжело ранена",
    "тяжело пострадал",
    "тяжело пострадала",
    "критическом состоянии",
]

# Score ранжирует только уже допущенные hard true crime материалы.
# Слабые темы дают лишь небольшие бонусы и не могут открыть фильтр.
SCORE_RULES = {
    "убий": 10,
    "убил": 10,
    "убит": 10,
    "изнасил": 9,
    "расстрел": 9,
    "застрел": 9,
    "самоубий": 7,
    "суицид": 7,
    "покончил с собой": 7,
    "покончила с собой": 7,
    "гибел": 7,
    "погиб": 7,
    "скончал": 7,
    "смерт": 7,
    "тяжкий вред": 7,
    "тяжёлый вред": 7,
    "тяжелый вред": 7,
    "угроза жизни": 7,
    "угрозой жизни": 7,
    "несколько жертв": 7,
    "множественные жертвы": 7,
    "тяжело ранен": 7,
    "тяжело ранена": 7,
    "тяжело пострадал": 7,
    "тяжело пострадала": 7,
    "критическом состоянии": 7,
    "покушен": 1,
    "ограб": 1,
    "похищ": 1,
    "мошеннич": 1,
    "избил": 1,
    "избиен": 1,
    "нападен": 1,
    "стрельб": 1,
    "вооруж": 1,
    "краж": 1,
    "наркот": 1,
    "уголовн": 1,
    "преступ": 1,
    "задерж": 1,
    "арест": 1,
    "подозрев": 1,
    "приговор": 1,
    "осужден": 1,
    "осуждён": 1,
    "пропал": 1,
    "пропав": 1,
    "следств": 1,
    "полици": 1,
    "обвин": 1,
    "розыск": 1,
    "разыск": 1,
}
