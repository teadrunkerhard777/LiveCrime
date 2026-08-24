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
# но не записывает выбранные материалы в storage/published.json.
DRY_RUN = True


# Основной режим публикации:
# каждая выбранная новость отправляется отдельным постом.
POST_MODE = "single"


# Тематики, которые интересуют наш канал.
# Используем основы слов, чтобы одной записью находить разные окончания:
# например, "обвин" совпадёт с "обвиняемый" и "обвинили".
TOPICS = [
    # Основные тяжкие преступления.
    "убий",
    "покушен",
    "ограб",
    "похищ",
    "мошеннич",
    "задерж",
    "арест",
    "нападен",
    "изнасил",
    "расстрел",

    # Расследование, розыск и работа правоохранительных органов.
    "уголовн",
    "преступ",
    "следств",
    "полици",
    "обвин",
    "подозрев",
    "розыск",
    "разыск",

    # Судебные решения и наказания.
    # Не используем слишком общий корень "суд": он встречается
    # внутри посторонних слов, например "государственный".
    "судебн",
    "приговор",
    "осужден",
    "осуждён",

    # Исчезновения людей и сообщения об обнаружении погибших.
    "пропал",
    "пропав",
    "обнаружен труп",
    "обнаружили тело",
    "нашли тело",

    # Частые формы региональных криминальных заголовков.
    "избил",
]


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
        "enabled": False,
        "url": "https://www.sarbc.ru/rss/data-utf/event.rss",
    },

    # Москва
    {
        "name": "АГН Москва: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://www.mskagency.ru/rss/incident.rss",
    },

    # Москва + Московская область
    {
        "name": "StolicaMedia: происшествия Москвы и области",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://stolicamedia.ru/export/new/newsByRubric_121_188.rss",
    },

    # Санкт-Петербург
    {
        "name": "PeterburgMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://peterburgmedia.ru/export/new/newsByRubric_88_198.rss",
    },

    # Краснодарский край
    {
        "name": "KrasnodarMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://krasnodarmedia.su/export/new/newsByRubric_25_79.rss",
    },

    # Сибирь: Иркутская область
    {
        "name": "IrkutskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://irkutskmedia.ru/export/new/newsByRubric_14_51.rss",
    },

    # Сибирь: Красноярский край
    {
        "name": "KrasnoyarskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://krasnoyarskmedia.ru/export/new/newsByRubric_26_16.rss",
    },

    # Сибирь: Омская область
    {
        "name": "OmskMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://omskmedia.su/export/new/newsByRubric_38_181.rss",
    },

    # Дальний Восток: Приморский край
    {
        "name": "PrimaMedia: происшествия Приморья",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://primamedia.ru/export/new/newsByRubric_43_19.rss",
    },

    # Дальний Восток: Хабаровский край
    {
        "name": "AmurMedia: происшествия Хабаровского края",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://amurmedia.ru/export/new/newsByRubric_77_27.rss",
    },

    # Дальний Восток: Сахалин
    {
        "name": "SakhalinMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://sakhalinmedia.ru/export/new/newsByRubric_64_40.rss",
    },

    # Дальний Восток: Якутия
    {
        "name": "YakutiaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://yakutiamedia.ru/export/new/newsByRubric_55_71.rss",
    },

    # Дальний Восток: Амурская область
    {
        "name": "PriamurMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://priamurmedia.ru/export/new/newsByRubric_2_121.rss",
    },

    # Дальний Восток: Камчатка
    {
        "name": "KamchatkaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://kamchatkamedia.ru/export/new/newsByRubric_18_118.rss",
    },

    # Дальний Восток: Еврейская автономная область
    {
        "name": "EAOMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://eaomedia.ru/export/new/newsByRubric_11_35.rss",
    },

    # Дальний Восток: Магаданская область
    {
        "name": "MagadanMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://magadanmedia.ru/export/new/newsByRubric_31_63.rss",
    },

    # Дальний Восток: Чукотка
    {
        "name": "ChukotkaMedia: происшествия",
        "type": "rss",
        "role": "article_source",
        "enabled": False,
        "url": "https://chukotkamedia.ru/export/new/newsByRubric_83_44.rss",
    },

    # HTML-источники используют отдельные адаптеры.
    # Полный текст статьи по-прежнему загружается позже через article/fetcher.py.
    {
        "name": "116.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
        "url": "https://116.ru/text/incidents/",
        "adapter": "116ru",
        "timezone": "Europe/Moscow",
        "limit": 40,
    },
    {
        "name": "E1.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
        "url": "https://www.e1.ru/text/incidents/",
        "adapter": "e1ru",
        "timezone": "Asia/Yekaterinburg",
        "limit": 40,
    },
    {
        "name": "VN.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
        "url": "https://vn.ru/news/proisshestviya/",
        "adapter": "vnru",
        "timezone": "Asia/Novosibirsk",
        "limit": 40,
    },
    {
        "name": "vtomske.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
        "url": "https://vtomske.ru/tag/incident",
        "adapter": "vtomske",
        "timezone": "Asia/Tomsk",
        "limit": 40,
    },
    {
        "name": "Amic.ru: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
        "url": "https://www.amic.ru/news/incident",
        "adapter": "amic",
        "timezone": "Asia/Barnaul",
        "limit": 40,
    },
    {
        "name": "A42: происшествия",
        "type": "html",
        "role": "article_source",
        "enabled": False,
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

# Слова и выражения, которые подтверждают,
# что речь идёт о реальном преступлении или расследовании.
CRIME_CONTEXT_KEYWORDS = [
    "задержан",
    "задержали",
    "арестован",
    "арестовали",
    "подозреваемый",
    "подозревается",
    "обвиняемый",
    "обвиняется",
    "полиция",
    "следствие",
    "следственный комитет",
    "возбуждено уголовное дело",
    "уголовное дело",
    "суд",
    "потерпевший",
    "потерпевшая",
    "погиб",
    "погибла",
    "убит",
    "убита",
]

# Весовые коэффициенты для рейтинга новости.
# Чем выше итоговый score, тем выше новость будет в подборке.
SCORE_RULES = {
    "убийство": 3,
    "похищение": 3,
    "ограбление": 2,
    "покушение": 2,
    "задержан": 2,
    "арестован": 2,
    "приговор": 2,
    "расследование": 1,
    "подозреваемый": 1,
    "следствие": 1,
}
