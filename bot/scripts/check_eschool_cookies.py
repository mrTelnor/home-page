"""Одноразовый smoke-чек cookie-режима ESchoolClient.

Запуск:
    cd bot
    ./.venv/Scripts/python.exe scripts/check_eschool_cookies.py "<cookie-string>"
"""
import asyncio
import sys
from datetime import date

from app.eschool.client import ESchoolClient, EschoolAuthError
from app.eschool.parser import parse_grades, parse_homework
from app.eschool.service import next_school_day, week_range_ms


async def main(cookie_header: str) -> int:
    client = ESchoolClient(
        base_url="https://app.eschool.center/ec-server",
        cookie_header=cookie_header,
    )
    try:
        try:
            await client.connect()
        except EschoolAuthError as exc:
            print(f"AUTH FAIL: {exc}")
            return 1

        print(f"connected ok (cookies_mode={client.cookies_mode})")
        print(f"  parent_prs_id = {client.parent_prs_id}")
        print(f"  children      = {client.children}")
        print(f"  default child = {client.default_child_prs_id}")

        child_id = client.default_child_prs_id
        if child_id is None:
            print("no child in state — cannot fetch diary")
            return 2

        today = date.today()
        target = next_school_day(today)
        d1, d2 = week_range_ms(target)
        print(f"\nfetching diary for child={child_id}, target_day={target}")
        diary = await client.get_diary(child_id, d1, d2)

        hw = parse_homework(diary, target)
        grades = parse_grades(diary, today)
        print(f"  homework items on {target}: {len(hw)}")
        for item in hw[:3]:
            print(f"    - {item.lesson_name}: {item.task[:80] if item.task else '<empty>'}")
        print(f"  grades today ({today}): {len(grades)}")
        for g in grades[:3]:
            print(f"    - {g.lesson_name}: {g.mark}")
        return 0
    finally:
        await client.aclose()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/check_eschool_cookies.py '<cookie-string>'")
        sys.exit(64)
    sys.exit(asyncio.run(main(sys.argv[1])))
