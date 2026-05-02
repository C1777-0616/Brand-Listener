import asyncio
import os
from xhs import AsyncXhsClient
from dotenv import load_dotenv

load_dotenv()

cookie = os.getenv("COOKIES", "").strip()
target_user_id = os.getenv("XHS_TARGET_USER_ID", "").strip()

if not cookie:
    raise ValueError("缺少环境变量 COOKIES，请在 .env 中配置。")
if not target_user_id:
    raise ValueError("缺少环境变量 XHS_TARGET_USER_ID，请在 .env 中配置。")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Referer": "https://www.xiaohongshu.com/",
    "Cookie": cookie,
}
PROXIES = {}

async def crawl_target_users():
    client = AsyncXhsClient(headers=HEADERS, proxies=PROXIES)
    user_id = target_user_id
    
    try:
        user_info = await client.get_user_info(user_id=user_id)
        user_notes = await client.get_user_notes(user_id=user_id, page=1)
        print("博主昵称：", user_info.get("nickname"))
        print("粉丝数：", user_info.get("fans"))
        print("笔记数：", len(user_notes))
    except Exception as e:
        print("报错原因：", e)

if __name__ == "__main__":
    asyncio.run(crawl_target_users())