# Qwen Code Stats Tracker

Трекер для отслеживания статистики использования Qwen Code CLI по сессиям в разных проектах.

## Возможности

- 📊 Статистика по каждому проекту отдельно
- 📈 Общая агрегированная статистика по всем проектам
- 📅 Фильтрация по дате или периоду
- 🔍 Автообнаружение всех проектов из `.qwen/projects/`
- 📋 Детальная информация:
  - Interaction Summary (сессии, tool calls, success rate, код)
  - Performance (wall time, agent active, API time, tool time)
  - Model Usage (токены, cache efficiency)
  - Top Tools (топ используемых инструментов)

## Установка

Нужен только Python 3.8+:

```bash
# Скрипт не требует установки зависимостей
python qwen-stats-tracker.py --help
```

## Использование

### Статистика за вчера (по умолчанию)

```bash
python qwen-stats-tracker.py
```

### Статистика за конкретную дату

```bash
python qwen-stats-tracker.py --date 2026-04-12
```

### Статистика за период

```bash
python qwen-stats-tracker.py --start 2026-04-10 --end 2026-04-13
```

### Статистика по конкретному проекту

```bash
python qwen-stats-tracker.py --project schedule-bot --date 2026-04-12
```

Или по частичному совпадению:

```bash
python qwen-stats-tracker.py --project obsidian
```

### Список всех проектов

```bash
python qwen-stats-tracker.py --help
```

Автообнаружение найдёт все проекты в `.qwen/projects/`. Для удобных имён используется словарь алиасов (schedule-bot, obsidian, satella, gleb7-home).

## Формат вывода

```
================================================================================
📊 Проект: schedule-bot
📅 Период: 2026-04-12 — 2026-04-13
================================================================================

📈 Interaction Summary
  Сессий: 15
  Tool Calls: 1272
  Success Rate: 95.6%
  Code Changes: +3297 -103

⏱️  Performance
  Wall Time: 11h 44m 1s
  Agent Active: 10h 46m 50s
    » API Time: 9h 23m 12s
    » Tool Time: 1h 23m 37s

🤖 Model Usage
  Model                Reqs     Input Tokens    Output Tokens
  ------------------ ------ ------------- -------------
  coder-model          867      103,331,471     373,105

  Savings Highlight: 97,990,088 (94.8%) of input tokens were served from cache

🔧 Top Tools:
  read_file: 506
  run_shell_command: 197
  edit: 174
  ...
================================================================================
```

## Как это работает

Скрипт автоматически сканирует `.qwen/projects/*/chats/` и находит все проекты с сессиями. Не нужно ничего настраивать!

Для удобства некоторые проекты имеют алиасы:
- `schedule-bot` → `c--users-gleb7-onedrive--------------vibecoding-projects-schedule-bot-main-codexnew`
- `obsidian` → `c--users-gleb7-onedrive--------------vibecoding-obsidian`
- `satella` → `c--users-gleb7-onedrive--------------vibecoding-projects-satella`
- `gleb7-home` → `C--Users-gleb7`

Новые проекты автоматически обнаруживаются по их sanitised имени папки.

## Что парсится

Скрипт читает `.jsonl` файлы сессий из директорий `.qwen/projects/<project>/chats/`, парсит записи и агрегирует:

- **API Responses** — запросы к модели, токены, cache
- **Tool Calls** — вызовы инструментов, успешность, длительность
- **Временные метки** — wall time, agent active time

## Данные по проектам (пример за 12 апреля 2026)

### schedule-bot-main_codexnew
- Сессий: 15
- Tool Calls: 1272
- Success Rate: 95.6%
- Input Tokens: ~103M
- Cache: 94.8%

### Obsidian
- Сессий: 15
- Tool Calls: 1537
- Success Rate: 90.2%
- Input Tokens: ~79M
- Cache: 87.1%

### Все проекты вместе
- Сессий: 32
- Tool Calls: 3130
- Success Rate: 95.6%
- Input Tokens: ~201M
- Cache: 91.0%

## Лицензия

MIT
