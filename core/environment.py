import os

import certifi


def configure_ssl():
    """Указывает HTTPS-клиентам актуальный набор корневых сертификатов."""

    # certifi поставляет проверенный CA bundle вместе с зависимостями проекта.
    # setdefault сохраняет явно заданную пользователем настройку окружения.
    os.environ.setdefault(
        "SSL_CERT_FILE",
        certifi.where(),
    )

    # SSL-проверку намеренно не отключаем: verify=False сделал бы
    # загрузку новостей уязвимой для подмены HTTPS-соединения.
    return os.environ["SSL_CERT_FILE"]
