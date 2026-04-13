#!/usr/bin/env python3
"""
Qwen Code Session Stats Tracker
Собирает и агрегирует статистику использования Qwen Code CLI по сессиям
Автообнаружение проектов из .qwen/projects/
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Any, Tuple

# Базовая директория с проектами Qwen Code
# Определяется автоматически из домашней директории пользователя
USER_HOME = os.path.expanduser("~")
QWEN_PROJECTS_DIR = os.path.join(USER_HOME, ".qwen", "projects")


def sanitize_to_name(sanitized: str) -> str:
    """Преобразует sanitised имя папки в короткое читаемое"""
    # Разбиваем по разделителям и убираем системные части
    parts = sanitized.split("-")
    skip = {"c", "users", "onedrive", "", "vibecoding", "projects", "desktop", "рабочий", "стол"}
    filtered = [p for p in parts if p.lower() not in skip]
    
    if not filtered:
        return sanitized
    
    # Для домашних директорий (C--Users-username) берём "username-home"
    if len(filtered) == 1 and filtered[0].lower() not in ["obsidian", "satella", "schedule", "codexnew"]:
        return f"{filtered[0]}-home"
    
    # Для остальных берём последнюю значимую часть
    return filtered[-1]


def discover_projects() -> Dict[str, str]:
    """Автоматически находит все проекты в .qwen/projects/"""
    projects = {}
    
    if not os.path.exists(QWEN_PROJECTS_DIR):
        print(f"⚠️  Директория {QWEN_PROJECTS_DIR} не найдена!", file=sys.stderr)
        return projects
    
    for project_dir in os.listdir(QWEN_PROJECTS_DIR):
        project_path = os.path.join(QWEN_PROJECTS_DIR, project_dir)
        chats_dir = os.path.join(project_path, "chats")
        
        if os.path.isdir(project_path) and os.path.exists(chats_dir):
            # Автоматически генерируем короткое имя из sanitised пути
            short_name = sanitize_to_name(project_dir)
            projects[short_name] = chats_dir
    
    return projects


def parse_session_file(filepath: str) -> Dict[str, Any]:
    """Парсит jsonl файл сессии и извлекает статистику"""
    stats = {
        "session_id": Path(filepath).stem,
        "start_time": None,
        "end_time": None,
        "tool_calls": [],
        "api_responses": [],
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cached_tokens": 0,
        "total_requests": 0,
        "code_changes": {"added": 0, "removed": 0},
        "tool_stats": defaultdict(lambda: {"calls": 0, "success": 0, "fail": 0, "duration_ms": 0}),
    }

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = record.get("timestamp")
                if timestamp:
                    if stats["start_time"] is None:
                        stats["start_time"] = timestamp
                    stats["end_time"] = timestamp

                # API Response - токены
                if record.get("subtype") == "ui_telemetry":
                    event = record.get("systemPayload", {}).get("uiEvent", {})
                    event_name = event.get("event.name", "")
                    
                    if "api_response" in event_name:
                        stats["total_requests"] += 1
                        stats["total_input_tokens"] += event.get("input_token_count", 0)
                        stats["total_output_tokens"] += event.get("output_token_count", 0)
                        stats["total_cached_tokens"] += event.get("cached_content_token_count", 0)
                        stats["api_responses"].append(event)
                    
                    elif "tool_call" in event_name:
                        tool_name = event.get("function_name", "unknown")
                        duration = event.get("duration_ms", 0)
                        success = event.get("success", False)
                        
                        stats["tool_calls"].append(event)
                        stats["tool_stats"][tool_name]["calls"] += 1
                        stats["tool_stats"][tool_name]["duration_ms"] += duration
                        if success:
                            stats["tool_stats"][tool_name]["success"] += 1
                        else:
                            stats["tool_stats"][tool_name]["fail"] += 1

                # Code changes - из tool_result с diff
                elif record.get("type") == "tool_result":
                    # Путь 1: message.parts[0].functionResponse.name
                    parts = record.get("message", {}).get("parts", [])
                    if parts:
                        func_response = parts[0].get("functionResponse", {})
                        tool_name = func_response.get("name", "")
                        
                        if tool_name in ["write_file", "edit"]:
                            # Путь 2: toolCallResult.resultDisplay.diffStat
                            tool_result = record.get("toolCallResult", {})
                            result_display = tool_result.get("resultDisplay", {})
                            
                            if isinstance(result_display, dict):
                                diff_stat = result_display.get("diffStat", {})
                                if diff_stat:
                                    stats["code_changes"]["added"] += diff_stat.get("model_added_lines", 0)
                                    stats["code_changes"]["removed"] += diff_stat.get("model_removed_lines", 0)

    except Exception as e:
        print(f"Ошибка при чтении {filepath}: {e}", file=sys.stderr)
        return None

    return stats


def calculate_session_duration(start: str, end: str) -> float:
    """Вычисляет длительность сессии в секундах"""
    if not start or not end:
        return 0
    try:
        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
        return (end_dt - start_dt).total_seconds()
    except:
        return 0


def format_duration(seconds: float) -> str:
    """Форматирует секунды в читаемый вид"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def aggregate_stats(sessions: List[Dict]) -> Dict:
    """Агрегирует статистику по всем сессиям"""
    aggregated = {
        "total_sessions": len(sessions),
        "total_wall_time": 0,
        "total_api_time": 0,
        "total_tool_time": 0,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_cached_tokens": 0,
        "total_requests": 0,
        "tool_calls": defaultdict(int),
        "code_added": 0,
        "code_removed": 0,
        "success_rate": 0,
        "total_tool_calls": 0,
        "successful_tool_calls": 0,
    }

    for session in sessions:
        if session is None:
            continue
        
        duration = calculate_session_duration(session["start_time"], session["end_time"])
        aggregated["total_wall_time"] += duration
        
        aggregated["total_input_tokens"] += session["total_input_tokens"]
        aggregated["total_output_tokens"] += session["total_output_tokens"]
        aggregated["total_cached_tokens"] += session["total_cached_tokens"]
        aggregated["total_requests"] += session["total_requests"]
        
        aggregated["code_added"] += session["code_changes"]["added"]
        aggregated["code_removed"] += session["code_changes"]["removed"]
        
        for tool_name, tool_stat in session["tool_stats"].items():
            aggregated["tool_calls"][tool_name] += tool_stat["calls"]
            aggregated["total_tool_calls"] += tool_stat["calls"]
            aggregated["successful_tool_calls"] += tool_stat["success"]
            aggregated["total_tool_time"] += tool_stat["duration_ms"] / 1000  # в секунды
        
        # API time примерно = total tokens processing time
        # Это грубая оценка
        aggregated["total_api_time"] += duration * 0.8  # примерно 80% времени - API

    if aggregated["total_tool_calls"] > 0:
        aggregated["success_rate"] = (aggregated["successful_tool_calls"] / aggregated["total_tool_calls"]) * 100

    return aggregated


def print_stats(aggregated: Dict, project_name: str = None, date_range: str = None):
    """Выводит статистику в читаемом виде"""
    print("\n" + "="*80)
    if project_name:
        print(f"📊 Проект: {project_name}")
    if date_range:
        print(f"📅 Период: {date_range}")
    print("="*80)

    print(f"\n📈 Interaction Summary")
    print(f"  Сессий: {aggregated['total_sessions']}")
    print(f"  Tool Calls: {aggregated['total_tool_calls']}")
    print(f"  Success Rate: {aggregated['success_rate']:.1f}%")
    print(f"  Code Changes: +{aggregated['code_added']} -{aggregated['code_removed']}")

    print(f"\n⏱️  Performance")
    print(f"  Wall Time: {format_duration(aggregated['total_wall_time'])}")
    print(f"  Agent Active: {format_duration(aggregated['total_api_time'] + aggregated['total_tool_time'])}")
    print(f"    » API Time: {format_duration(aggregated['total_api_time'])}")
    print(f"    » Tool Time: {format_duration(aggregated['total_tool_time'])}")

    print(f"\n🤖 Model Usage")
    print(f"  {'Model':<20} {'Reqs':<8} {'Input Tokens':<15} {'Output Tokens':<15}")
    print(f"  {'-'*18} {'-'*6} {'-'*13} {'-'*13}")
    print(f"  {'coder-model':<20} {aggregated['total_requests']:<8} {aggregated['total_input_tokens']:<15,} {aggregated['total_output_tokens']:<15,}")

    cache_pct = 0
    if aggregated['total_input_tokens'] > 0:
        cache_pct = (aggregated['total_cached_tokens'] / aggregated['total_input_tokens']) * 100
    print(f"\n  Savings Highlight: {aggregated['total_cached_tokens']:,} ({cache_pct:.1f}%) of input tokens were served from cache")

    if aggregated['tool_calls']:
        print(f"\n🔧 Top Tools:")
        sorted_tools = sorted(aggregated['tool_calls'].items(), key=lambda x: x[1], reverse=True)[:10]
        for tool, count in sorted_tools:
            print(f"  {tool}: {count}")

    print("="*80)


def filter_sessions_by_date(sessions: List[Dict], start_date: str, end_date: str = None) -> List[Dict]:
    """Фильтрует сессии по периоду дат"""
    filtered = []
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
    else:
        end_dt = start_dt + timedelta(days=1)
    
    for session in sessions:
        if session and session["start_time"]:
            try:
                session_dt = datetime.fromisoformat(session["start_time"].replace('Z', '+00:00'))
                session_naive = session_dt.replace(tzinfo=None)
                if start_dt <= session_naive < end_dt:
                    filtered.append(session)
            except:
                pass
    
    return filtered


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Qwen Code Session Stats Tracker')
    parser.add_argument('--date', type=str, help='Фильтр по дате (YYYY-MM-DD), например 2026-04-12')
    parser.add_argument('--start', type=str, help='Начальная дата периода (YYYY-MM-DD)')
    parser.add_argument('--end', type=str, help='Конечная дата периода (YYYY-MM-DD)')
    parser.add_argument('--project', type=str, help='Фильтр по проекту')
    parser.add_argument('--all', action='store_true', help='Показать статистику по всем проектам')
    args = parser.parse_args()

    # Определяем дату/период
    if args.date:
        start_date = args.date
        end_date = None
    elif args.start:
        start_date = args.start
        end_date = args.end
    else:
        # По умолчанию - вчера
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        end_date = None

    # Определяем проекты для анализа
    all_projects = discover_projects()
    
    if not all_projects:
        print("❌ Не найдено ни одного проекта с сессиями!")
        print(f"Проверьте директорию: {QWEN_PROJECTS_DIR}")
        sys.exit(1)
    
    projects_to_analyze = all_projects
    if args.project:
        # Ищем проект по алиасу или по частичному совпадению
        matched = None
        for name in all_projects.keys():
            if args.project.lower() in name.lower():
                matched = name
                break
        
        if matched:
            projects_to_analyze = {matched: all_projects[matched]}
        else:
            print(f"Проект '{args.project}' не найден. Доступные проекты:")
            for name in all_projects.keys():
                print(f"  - {name}")
            sys.exit(1)

    date_range = start_date
    if end_date:
        date_range = f"{start_date} — {end_date}"

    total_aggregated = None

    for project_name, chats_dir in projects_to_analyze.items():
        if not os.path.exists(chats_dir):
            print(f"⚠️  Директория {chats_dir} не найдена, пропускаем...")
            continue

        # Собираем все сессии
        all_sessions = []
        for filename in os.listdir(chats_dir):
            if filename.endswith('.jsonl'):
                filepath = os.path.join(chats_dir, filename)
                stats = parse_session_file(filepath)
                if stats:
                    all_sessions.append(stats)

        # Фильтруем по дате если нужно
        if start_date:
            sessions = filter_sessions_by_date(all_sessions, start_date, end_date)
        else:
            sessions = all_sessions

        if not sessions:
            continue

        # Агрегируем и выводим
        aggregated = aggregate_stats(sessions)

        # Пропускаем проекты с нулевой активностью
        if aggregated["total_tool_calls"] == 0 and aggregated["total_requests"] == 0:
            continue

        print_stats(aggregated, project_name, date_range)

        # Суммируем для общей статистики
        if total_aggregated is None:
            total_aggregated = aggregated
        else:
            for key in ['total_sessions', 'total_wall_time', 'total_api_time', 'total_tool_time',
                       'total_input_tokens', 'total_output_tokens', 'total_cached_tokens',
                       'total_requests', 'code_added', 'code_removed', 'total_tool_calls',
                       'successful_tool_calls']:
                total_aggregated[key] += aggregated[key]
            
            for tool, count in aggregated['tool_calls'].items():
                total_aggregated['tool_calls'][tool] += count

    # Выводим общую статистику если анализируем несколько проектов
    if len(projects_to_analyze) > 1 and total_aggregated:
        print_stats(total_aggregated, "ВСЕ ПРОЕКТЫ", date_range)


if __name__ == "__main__":
    main()
