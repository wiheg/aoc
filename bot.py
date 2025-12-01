import time
import asyncio
import requests
import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import *

CACHE_TTL = 60 * 15
_cache_data = None
_cache_timestamp = 0
_last_star = -1
_last_day = 0


def init_globals():
    global _last_star
    global _last_day
    with open("globals.txt", "r") as f:
        _last_star = int(f.readline())
        _last_day = int(f.readline())


def save_globals():
    with open("globals.txt", "w") as f:
        f.write(str(_last_star))
        f.write("\n")
        f.write(str(_last_day))


def get_leaderboard(force_refresh=False):
    global _cache_data, _cache_timestamp
    now = time.time()
    if not force_refresh and _cache_data and (now - _cache_timestamp < CACHE_TTL):
        return _cache_data
    r = requests.get(URL, cookies={"session": COOKIE})
    _cache_data = r.json()
    _cache_timestamp = now
    return _cache_data


def format_leaderboard(data):
    members = data["members"]
    sorted_members = sorted(
        members.values(),
        key=lambda m: (-m["local_score"], m["stars"])
    )
    out = [f"★ *Advent of Code — Наш Leaderboard* ★\n"]
    for member in sorted_members:
        score = member["local_score"]
        stars = member["stars"]
        name = member["name"]
        out.append(f"*{name}* : {stars} ★ — {score} очков\n")
    return "\n".join(out)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def leaderboard_keyboard():
    kb = InlineKeyboardBuilder()
    for day in range(1, 13):
        kb.button(text=f"День {day}", callback_data=f"day:{day}")
    kb.button(text="Общее", callback_data=f"day:{0}")
    kb.adjust(4, 4, 4, 1)
    return kb.as_markup()


async def check_new_stars():
    global _last_star
    data = get_leaderboard()
    mx = _last_star
    for member in data["members"].values():
        name = member["name"]
        for day in member["completion_day_level"]:
            day_res = member["completion_day_level"][day]
            if day_res["1"]["star_index"] > _last_star:
                mx = max(mx, day_res["1"]["star_index"])
                await bot.send_message(NOTIFY_CHAT_ID, f"{name} получил первую звезду за день {int(day)}! ★",
                                       parse_mode=ParseMode.MARKDOWN)
            if day_res["2"]["star_index"] > _last_star:
                mx = max(mx, day_res["2"]["star_index"])
                await bot.send_message(NOTIFY_CHAT_ID, f"{name} получил вторую звезду за день {int(day)}! ★★",
                                       parse_mode=ParseMode.MARKDOWN)
    _last_star = mx


async def notify_new_day():
    global _last_day
    today = (datetime.datetime.now() - datetime.timedelta(hours=8)).day
    if today != _last_day:
        _last_day = today
        await bot.send_message(NOTIFY_CHAT_ID, f"🎄День {today} уже доступен!", parse_mode=ParseMode.MARKDOWN)


async def scheduler():
    while True:
        print(f"scheduler...{datetime.datetime.now()}")
        try:
            await check_new_stars()
            await notify_new_day()
            save_globals()
        except Exception:
            pass
        await asyncio.sleep(CACHE_TTL * 1000)


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        f"лидерборд: /leaderboard\nдобавиться в группу на сайте https://adventofcode.com/2025/leaderboard/private\nкод: {GROUP}")


@dp.message(Command("leaderboard"))
async def leaderboard(message: types.Message):
    data = get_leaderboard()
    text = format_leaderboard(data)
    await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=leaderboard_keyboard())


@dp.callback_query(lambda c: c.data.startswith("day:"))
async def cb_day(callback: types.CallbackQuery):
    await callback.answer()
    day = int(callback.data.split(":")[1])
    data = get_leaderboard()
    if day == 0:
        await callback.message.edit_text(format_leaderboard(data), parse_mode=ParseMode.MARKDOWN,
                                         reply_markup=leaderboard_keyboard())
        return
    out = [f"*День {day}* — результаты\n"]
    for member in data["members"].values():
        name = member["name"]
        if str(day) not in member["completion_day_level"]:
            continue
        stars = member["completion_day_level"]
        star1 = stars[str(day)]["1"]
        star2 = stars[str(day)]["2"]
        line = f"*{name}*: "
        if star1:
            line += "★"
        if star2:
            line += "★"
        out.append(line)
    if len(out) == 1:
        out.append("_Никто пока не проходил этот день._")
    text = "\n".join(out)
    await callback.message.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=leaderboard_keyboard())


async def main():
    init_globals()
    asyncio.create_task(scheduler())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
