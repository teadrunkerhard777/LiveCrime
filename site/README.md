# LiveCrime Site

Отдельный статический сайт проекта LiveCrime. Он не публикует сообщения в
Telegram и не изменяет состояние криминального автопостера.

Сейчас внутри находится только изолированный Astro-каркас с одной вымышленной
демонстрационной карточкой. Подключения к `storage/published.json` пока нет.

## Локальный запуск

```bash
npm install
npm run dev
```

Проверка типов и production-сборка:

```bash
npm run build
```

## Временный адрес GitHub Pages

Для этого репозитория production-сборка использует временный адрес:

```text
https://teadrunkerhard777.github.io/LiveCrime/
```

Локально такую же структуру адресов можно проверить командой:

```bash
SITE_URL=https://teadrunkerhard777.github.io \
BASE_PATH=/LiveCrime npm run build
```

Отдельный `.github/workflows/site.yml` собирает только папку `site/`. Он не
запускает автопостер, не получает Telegram secrets и не изменяет
`storage/published.json`.

Чтобы выполнить первое развёртывание, после отправки файлов в GitHub необходимо
один раз выбрать **GitHub Actions** как источник публикации в настройках Pages
репозитория. Подключение собственного домена позднее не потребует переписывать
контент.

Подробный план находится в [ROADMAP.md](./ROADMAP.md).
