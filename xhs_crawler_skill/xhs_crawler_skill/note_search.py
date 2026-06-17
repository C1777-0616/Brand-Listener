import requests
import gzip
import json
from typing import Optional, Dict, Any, List
from datetime import datetime

try:
    import pandas as pd
    import openpyxl
    EXCEL_SUPPORT = True
except ImportError:
    EXCEL_SUPPORT = False
    print("⚠️  警告：未安装 pandas 或 openpyxl，无法导出 Excel")


class XHSNoteSearch:
    """小红书笔记搜索类"""
    
    def __init__(self, api_token: str):
        """
        初始化搜索类
        
        Args:
            api_token: API 访问令牌
        """
        self.base_url = "https://proxy-api.ainm.store"
        self.api_token = api_token
        self.endpoint = "/p/xiaohongshu/search-note/v2"
    
    def search(
        self,
        keyword: str,
        page: int = 1,
        sort: str = "general",
        note_type: str = "_0",
        note_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        搜索小红书笔记
        
        Args:
            keyword: 搜索关键词（必填）
            page: 页码，默认 1
            sort: 排序方式，默认 general
                - general: 综合排序
                - popularity_descending: 热度降序
                - time_descending: 时间降序
                - comment_descending: 评论数降序
                - collect_descending: 收藏数降序
            note_type: 笔记类型，默认 _0
                - _0: 通用
                - _1: 视频
                - _2: 普通
            note_time: 时间筛选（可选）
                - 一天内：一天内
                - 一周内：一周内
                - 半年内：半年内
        
        Returns:
            包含搜索结果的字典
        """
        url = f"{self.base_url}{self.endpoint}"
        
        headers = {
            "Authorization": f"Bearer {self.api_token}"
        }
        
        params = {
            "keyword": keyword,
            "page": page,
            "sort": sort
        }
        
        # 使用正确的参数名：note-time
        if note_time:
            params["note-time"] = note_time
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=60)
            response.raise_for_status()
            
            # 使用新的解析方法（支持 gzip）
            result = self._parse_response(response)
            
            # 修复：API 返回 code: 200 表示成功，不是 0
            if result and result.get("code") in [0, 200]:
                return {
                    "success": True,
                    "data": result.get("data", {}),
                    "message": "搜索成功"
                }
            elif result:
                return {
                    "success": False,
                    "error_code": result.get("code"),
                    "message": self._get_error_message(result.get("code"))
                }
            else:
                return {
                    "success": False,
                    "error_code": "PARSE_ERROR",
                    "message": "响应解析失败"
                }
        
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error_code": "TIMEOUT",
                "message": "请求超时，建议重试"
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error_code": "NETWORK_ERROR",
                "message": f"网络错误：{str(e)}"
            }
    
    def _parse_response(self, response) -> Optional[Dict[str, Any]]:
        """解析响应，支持 gzip 压缩"""
        raw = response.content
        
        try:
            # 尝试 gzip 解压
            decompressed = gzip.decompress(raw)
            return json.loads(decompressed.decode('utf-8'))
        except:
            # 尝试直接解码
            try:
                return json.loads(raw.decode('utf-8'))
            except:
                return None
    
    def _get_error_message(self, code: int) -> str:
        """获取错误码对应的中文说明"""
        error_messages = {
            100: "Token 无效或已失效",
            301: "采集失败，请重试",
            302: "超出速率限制",
            303: "超出每日配额",
            400: "参数错误",
            500: "内部服务器错误",
            600: "权限不足",
            601: "余额不足"
        }
        return error_messages.get(code, f"未知错误 (code: {code})")
    
    def format_results(self, search_result: Dict[str, Any]) -> str:
        """格式化输出搜索结果"""
        if not search_result.get("success"):
            return f"❌ 搜索失败：{search_result.get('message')}"
        
        data = search_result.get("data", {})
        items = data.get("items", [])
        
        if not items:
            return "ℹ️ 未找到相关笔记"
        
        output = []
        output.append(f"✅ 搜索成功，共找到 {len(items)} 条笔记\n")
        output.append("=" * 80)
        
        for idx, item in enumerate(items, 1):
            note = item.get("note", {})
            user = note.get("user", {})
            
            output.append(f"\n【{idx}】{note.get('id', 'N/A')}")
            output.append(f"标题：{note.get('desc', 'N/A')[:100]}...")
            output.append(f"作者：{user.get('nickname', 'N/A')} (ID: {user.get('userid', 'N/A')})")
            output.append(f"点赞：{note.get('liked_count', 0)} | 收藏：{note.get('collected_count', 0)} | 评论：{note.get('comments_count', 0)}")
            
            if note.get("images_list"):
                cover = note["images_list"][0].get("url", "")
                output.append(f"封面：{cover[:80]}...")
            
            output.append(f"类型：{note.get('type', 'N/A')}")
            
            timestamp = note.get("timestamp")
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                output.append(f"发布时间：{dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            output.append("-" * 80)
        
        return "\n".join(output)
    
    def search_all_pages(
        self,
        keyword: str,
        max_pages: int = 5,
        sort: str = "collect_descending",
        note_time: Optional[str] = None,
        delay_seconds: float = 2.0,
        deduplicate: bool = True
    ) -> Dict[str, Any]:
        """
        批量搜索多页笔记
        
        Args:
            keyword: 搜索关键词
            max_pages: 最大页数
            sort: 排序方式（默认 collect_descending，支持稳定翻页）
            note_time: 时间筛选
            delay_seconds: 每页延迟时间
            deduplicate: 是否去重（默认 True，基于笔记 ID 去重）
        
        Returns:
            包含所有笔记的字典
        """
        all_items = []
        consecutive_empty_pages = 0
        max_consecutive_empty = 2
        
        # 去重集合（基于笔记 ID）
        seen_note_ids = set() if deduplicate else None
        duplicate_count = 0
        
        for page in range(1, max_pages + 1):
            print(f"📄 采集第 {page} 页...")
            
            result = self.search(
                keyword=keyword,
                page=page,
                sort=sort,
                note_time=note_time
            )
            
            items = result.get("data", {}).get("items", [])
            
            if not result.get("success"):
                error_code = result.get("error_code")
                if error_code == 301 and items:
                    print(f"   ⚠️  第 {page} 页返回 301 但有 {len(items)} 条数据，继续采集")
                    # 去重处理
                    if deduplicate:
                        new_items = []
                        for item in items:
                            note_id = item.get("note", {}).get("id")
                            if note_id and note_id not in seen_note_ids:
                                new_items.append(item)
                                seen_note_ids.add(note_id)
                            else:
                                duplicate_count += 1
                        all_items.extend(new_items)
                    else:
                        all_items.extend(items)
                    consecutive_empty_pages = 0
                else:
                    print(f"   ❌ 第 {page} 页失败：{result.get('message')}")
                    if not items:
                        consecutive_empty_pages += 1
            else:
                if not items:
                    print(f"   ⚠️  第 {page} 页没有数据")
                    consecutive_empty_pages += 1
                else:
                    # 去重处理
                    if deduplicate:
                        new_items = []
                        for item in items:
                            note_id = item.get("note", {}).get("id")
                            if note_id and note_id not in seen_note_ids:
                                new_items.append(item)
                                seen_note_ids.add(note_id)
                            else:
                                duplicate_count += 1
                        all_items.extend(new_items)
                        print(f"   ✅ 获取 {len(items)} 条笔记（去重后 {len(new_items)} 条，重复 {duplicate_count} 条）")
                    else:
                        all_items.extend(items)
                        print(f"   ✅ 获取 {len(items)} 条笔记")
                    consecutive_empty_pages = 0
            
            if consecutive_empty_pages >= max_consecutive_empty:
                print(f"   🛑 连续 {max_consecutive_empty} 页无数据，停止采集")
                break
            
            if page < max_pages and consecutive_empty_pages < max_consecutive_empty:
                import time
                time.sleep(delay_seconds)
        
        return {
            "success": True,
            "data": {
                "items": all_items,
                "total_count": len(all_items),
                "duplicate_count": duplicate_count if deduplicate else 0
            },
            "message": f"成功采集 {len(all_items)} 条笔记" + (f"（已去除 {duplicate_count} 条重复）" if deduplicate and duplicate_count > 0 else "")
        }
    
    def export_to_excel(
        self,
        search_result: Dict[str, Any],
        filename: str
    ) -> bool:
        """
        导出搜索结果到 Excel 文件
        
        Args:
            search_result: 搜索结果
            filename: 输出文件名
        
        Returns:
            是否成功
        """
        if not EXCEL_SUPPORT:
            print("❌ 未安装 pandas 或 openpyxl，无法导出 Excel")
            return False
        
        if not search_result.get("success"):
            print("❌ 搜索失败，无法导出")
            return False
        
        items = search_result.get("data", {}).get("items", [])
        if not items:
            print("⚠️  没有数据可导出")
            return False
        
        print(f"\n📊 正在导出 {len(items)} 条笔记到 Excel...")
        
        # 提取数据
        data_rows = []
        for idx, item in enumerate(items, 1):
            note = item.get("note", {})
            user = note.get("user", {})
            
            # 转换时间戳为日期格式
            timestamp = note.get('timestamp')
            if timestamp and isinstance(timestamp, (int, float)):
                try:
                    publish_time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                except:
                    publish_time_str = str(timestamp)
            else:
                publish_time_str = str(timestamp) if timestamp else ''
            
            row = {
                '序号': idx,
                '笔记 ID': note.get('id', ''),
                '标题': note.get('desc', ''),
                '内容摘要': note.get('title', ''),
                '用户昵称': user.get('nickname', ''),
                '用户 ID': user.get('userid', ''),
                '小红书号': user.get('red_id', ''),
                '点赞数': note.get('liked_count', 0),
                '收藏数': note.get('collected_count', 0),
                '评论数': note.get('comments_count', 0),
                '分享数': note.get('share_count', 0),
                '类型': note.get('type', ''),
                '发布时间': publish_time_str,
                '封面图': note.get('images_list', [{}])[0].get('url', '') if note.get('images_list') else ''
            }
            data_rows.append(row)
        
        # 创建 DataFrame
        df = pd.DataFrame(data_rows)
        
        # 导出到 Excel
        try:
            df.to_excel(filename, index=False, engine='openpyxl')
            print(f"✅ 已导出到：{filename}")
            print(f"   共 {len(df)} 行")
            return True
        except Exception as e:
            print(f"❌ 导出失败：{e}")
            return False


def main():
    """主函数 - 示例用法"""
    api_token = input("请输入您的 API Token: ").strip()
    
    if not api_token:
        print("❌ API Token 不能为空！")
        return
    
    searcher = XHSNoteSearch(api_token)
    
    print("\n" + "=" * 80)
    print("小红书笔记搜索系统")
    print("=" * 80)
    
    keyword = input("\n请输入搜索关键词：").strip()
    if not keyword:
        print("❌ 关键词不能为空！")
        return
    
    print("\n选择排序方式：")
    print("1. 综合排序 (general)")
    print("2. 热度降序 (popularity_descending)")
    print("3. 时间降序 (time_descending)")
    print("4. 评论数降序 (comment_descending)")
    print("5. 收藏数降序 (collect_descending)")
    
    sort_choice = input("\n请选择 (1-5, 默认 1): ").strip()
    sort_map = {
        "1": "general",
        "2": "popularity_descending",
        "3": "time_descending",
        "4": "comment_descending",
        "5": "collect_descending"
    }
    sort = sort_map.get(sort_choice, "general")
    
    print("\n选择笔记类型：")
    print("1. 通用 (_0)")
    print("2. 视频 (_1)")
    print("3. 普通 (_2)")
    
    type_choice = input("\n请选择 (1-3, 默认 1): ").strip()
    type_map = {
        "1": "_0",
        "2": "_1",
        "3": "_2"
    }
    note_type = type_map.get(type_choice, "_0")
    
    print("\n时间筛选（可选）：")
    print("1. 一天内")
    print("2. 一周内")
    print("3. 半年内")
    print("4. 不筛选")
    
    time_choice = input("\n请选择 (1-4, 默认 4): ").strip()
    time_map = {
        "1": "一天内",
        "2": "一周内",
        "3": "半年内",
        "4": None
    }
    note_time = time_map.get(time_choice)
    
    page = input("\n请输入页码 (默认 1): ").strip()
    page = int(page) if page else 1
    
    print(f"\n🔍 正在搜索 \"{keyword}\" ...\n")
    
    result = searcher.search(
        keyword=keyword,
        page=page,
        sort=sort,
        note_type=note_type,
        note_time=note_time
    )
    
    print(searcher.format_results(result))


if __name__ == "__main__":
    main()
