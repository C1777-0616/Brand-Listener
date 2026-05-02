"""
FOLO 新帖子链接自动导出模块

通过 Playwright 浏览器自动化，从微博、小红书、B站抓取指定账号的最新帖子链接，
保存到 data/exports/ 目录并通过 API 返回。
"""
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class PostLink:
    """单条帖子链接数据"""

    def __init__(
        self,
        url: str,
        platform: str,
        source_url: str,
        title: str = "",
        published_at: Optional[str] = None,
        author: str = "",
        thumbnail: str = "",
    ):
        self.url = url
        self.platform = platform
        self.source_url = source_url
        self.title = title
        self.published_at = published_at or datetime.now().isoformat()
        self.author = author
        self.thumbnail = thumbnail

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "platform": self.platform,
            "source_url": self.source_url,
            "title": self.title,
            "published_at": self.published_at,
            "author": self.author,
            "thumbnail": self.thumbnail,
        }


class FOLOScraper:
    """
    Playwright-based FOLO 帖子链接导出器。
    支持微博、小红书、B站。
    """

    PLATFORM_SCRAPERS = {
        "weibo.com": "_scrape_weibo",
        "xiaohongshu.com": "_scrape_xhs",
        "xhslink.com": "_scrape_xhs",
        "bilibili.com": "_scrape_bilibili",
    }

    def __init__(self, export_dir: str = "./data/exports", headless: bool = True):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.headless = headless

    async def scrape_links(
        self,
        source_urls: List[str],
        max_posts: int = 20,
    ) -> Dict[str, Any]:
        """
        抓取给定账号 URL 列表中的最新帖子链接。

        Args:
            source_urls: 账号主页 URL 列表
            max_posts: 每个账号最多抓取帖子数

        Returns:
            {
                "links": [...],
                "errors": [...],
                "scraped_at": "...",
                "total": int
            }
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise RuntimeError(
                "playwright 未安装。请运行: pip install playwright && playwright install chromium"
            )

        all_links: List[PostLink] = []
        errors: List[Dict[str, str]] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="zh-CN",
            )

            for source_url in source_urls:
                try:
                    scraper_method = self._get_scraper(source_url)
                    if scraper_method is None:
                        errors.append({"url": source_url, "error": "不支持的平台"})
                        continue

                    page = await context.new_page()
                    try:
                        links = await scraper_method(page, source_url, max_posts)
                        all_links.extend(links)
                        logger.info(f"从 {source_url} 抓取到 {len(links)} 条帖子链接")
                    finally:
                        await page.close()

                except Exception as e:
                    logger.error(f"抓取 {source_url} 失败: {e}")
                    errors.append({"url": source_url, "error": str(e)})

            await browser.close()

        result = {
            "links": [lnk.to_dict() for lnk in all_links],
            "errors": errors,
            "scraped_at": datetime.now().isoformat(),
            "total": len(all_links),
        }

        self._save_to_file(result)

        return result

    def _get_scraper(self, source_url: str):
        """根据 URL 返回对应的平台爬虫方法"""
        url_lower = source_url.lower()
        for domain, method_name in self.PLATFORM_SCRAPERS.items():
            if domain in url_lower:
                return getattr(self, method_name)
        return None

    def _save_to_file(self, result: Dict[str, Any]) -> Path:
        """将抓取结果保存为带时间戳的 JSON 文件"""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = self.export_dir / f"folo_links_{ts}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        logger.info(f"帖子链接已保存至 {file_path}")
        return file_path

    # ── 平台爬虫 ──────────────────────────────────────────────────────────

    async def _scrape_weibo(self, page, source_url: str, max_posts: int) -> List[PostLink]:
        """抓取微博账号主页的最新帖子链接"""
        links: List[PostLink] = []

        try:
            await page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            if "m.weibo.cn" in source_url or "m.weibo.com" in source_url:
                # 移动版 m.weibo.cn
                items = await page.query_selector_all("div.card[mid]")
                for item in items[:max_posts]:
                    try:
                        mid = await item.get_attribute("mid")
                        if not mid:
                            continue
                        text_el = await item.query_selector(".txt")
                        title = ""
                        if text_el:
                            title = (await text_el.inner_text())[:80].strip()
                        time_el = await item.query_selector(".time")
                        pub = await time_el.inner_text() if time_el else ""
                        name_el = await item.query_selector(".name")
                        author = await name_el.inner_text() if name_el else ""
                        post_url = f"https://m.weibo.cn/detail/{mid}"
                        links.append(PostLink(
                            url=post_url,
                            platform="weibo",
                            source_url=source_url,
                            title=title,
                            published_at=pub,
                            author=author,
                        ))
                    except Exception as e:
                        logger.debug(f"解析微博卡片失败: {e}")
                        continue
            else:
                # 桌面版 weibo.com
                try:
                    await page.wait_for_selector("article, [class*='Feed_'], [class*='WB_feed']", timeout=10000)
                except Exception:
                    pass
                items = await page.query_selector_all("article, [class*='WB_feed_type']")
                for item in items[:max_posts]:
                    try:
                        link_el = await item.query_selector("a[href*='/status/'], a[href*='weibo.com/']")
                        if not link_el:
                            continue
                        href = await link_el.get_attribute("href")
                        if not href:
                            continue
                        if href.startswith("/"):
                            href = "https://weibo.com" + href
                        text_el = await item.query_selector("[class*='text'], [class*='content']")
                        title = ""
                        if text_el:
                            title = (await text_el.inner_text())[:80].strip()
                        links.append(PostLink(
                            url=href,
                            platform="weibo",
                            source_url=source_url,
                            title=title,
                            published_at=datetime.now().isoformat(),
                        ))
                    except Exception as e:
                        logger.debug(f"解析微博桌面版帖子失败: {e}")
                        continue

        except Exception as e:
            logger.error(f"微博抓取异常 {source_url}: {e}")

        return links

    async def _scrape_xhs(self, page, source_url: str, max_posts: int) -> List[PostLink]:
        """抓取小红书账号主页的最新笔记链接"""
        links: List[PostLink] = []

        try:
            await page.goto(source_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(4000)

            try:
                await page.wait_for_selector("a.cover, .note-item, section.note-item", timeout=10000)
            except Exception:
                pass

            items = await page.query_selector_all("section.note-item, .note-item")
            if not items:
                items = await page.query_selector_all("a.cover")

            for item in items[:max_posts]:
                try:
                    href = await item.get_attribute("href")
                    if not href:
                        link_el = await item.query_selector("a.cover, a[href*='/explore/']")
                        if not link_el:
                            continue
                        href = await link_el.get_attribute("href")
                    if not href:
                        continue
                    if href.startswith("/"):
                        href = "https://www.xiaohongshu.com" + href

                    title_el = await item.query_selector(".title, [class*='title']")
                    title = ""
                    if title_el:
                        title = (await title_el.inner_text())[:80].strip()

                    img_el = await item.query_selector("img")
                    thumbnail = await img_el.get_attribute("src") if img_el else ""

                    links.append(PostLink(
                        url=href,
                        platform="xiaohongshu",
                        source_url=source_url,
                        title=title,
                        published_at=datetime.now().isoformat(),
                        thumbnail=thumbnail or "",
                    ))
                except Exception as e:
                    logger.debug(f"解析小红书笔记失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"小红书抓取异常 {source_url}: {e}")

        return links

    async def _scrape_bilibili(self, page, source_url: str, max_posts: int) -> List[PostLink]:
        """抓取 B 站 UP 主空间的最新视频/动态链接"""
        links: List[PostLink] = []

        try:
            if "/space/" in source_url and not source_url.endswith("/video"):
                video_url = source_url.rstrip("/") + "/video"
            else:
                video_url = source_url

            await page.goto(video_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            try:
                await page.wait_for_selector("li.small-item, .bili-video-card", timeout=10000)
            except Exception:
                pass

            items = await page.query_selector_all("li.small-item, .bili-video-card")

            for item in items[:max_posts]:
                try:
                    link_el = await item.query_selector("a[href*='/video/BV'], a[href*='bilibili.com/video/']")
                    if not link_el:
                        link_el = await item.query_selector("a")
                    if not link_el:
                        continue

                    href = await link_el.get_attribute("href")
                    if not href:
                        continue
                    if href.startswith("//"):
                        href = "https:" + href
                    elif href.startswith("/"):
                        href = "https://www.bilibili.com" + href

                    title_el = await item.query_selector(".title, [class*='title']")
                    title = ""
                    if title_el:
                        title = (await title_el.inner_text())[:80].strip()

                    date_el = await item.query_selector(".date, [class*='pubdate']")
                    pub = await date_el.inner_text() if date_el else datetime.now().isoformat()

                    img_el = await item.query_selector("img")
                    thumbnail = ""
                    if img_el:
                        thumbnail = (
                            await img_el.get_attribute("src")
                            or await img_el.get_attribute("data-src")
                            or ""
                        )

                    links.append(PostLink(
                        url=href,
                        platform="bilibili",
                        source_url=source_url,
                        title=title,
                        published_at=pub,
                        thumbnail=thumbnail,
                    ))
                except Exception as e:
                    logger.debug(f"解析B站视频卡片失败: {e}")
                    continue

        except Exception as e:
            logger.error(f"B站抓取异常 {source_url}: {e}")

        return links


def load_latest_links(export_dir: str = "./data/exports") -> Dict[str, Any]:
    """读取 exports 目录中最新一次的链接抓取结果"""
    export_path = Path(export_dir)
    files = sorted(
        export_path.glob("folo_links_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return {"links": [], "total": 0, "scraped_at": None, "errors": []}

    with open(files[0], "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_links(export_dir: str = "./data/exports") -> List[Dict[str, Any]]:
    """合并 exports 目录中所有链接抓取文件，去重后返回"""
    export_path = Path(export_dir)
    seen_urls: set = set()
    all_links: List[Dict[str, Any]] = []

    for file in sorted(
        export_path.glob("folo_links_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for lnk in data.get("links", []):
                if lnk.get("url") not in seen_urls:
                    seen_urls.add(lnk["url"])
                    all_links.append(lnk)
        except Exception as e:
            logger.warning(f"读取 {file} 失败: {e}")

    return all_links
