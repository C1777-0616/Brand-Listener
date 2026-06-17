#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书笔记搜索 CLI 工具
"""
import sys
import json
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from note_search import XHSNoteSearch


def load_api_token():
    """从 .env 文件加载 API Token"""
    env_file = Path(__file__).parent / ".env"
    
    if not env_file.exists():
        print("❌ 未找到 .env 配置文件")
        print("💡 请先运行：python setup_guide.py 配置 API Token")
        sys.exit(1)
    
    # 读取 .env 文件
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('XHS_API_TOKEN='):
                return line.split('=', 1)[1].strip()
    
    print("❌ .env 文件中未找到 XHS_API_TOKEN")
    sys.exit(1)


def main():
    """CLI 主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='小红书笔记搜索工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python cli_search.py -k "Python 编程"
  python cli_search.py -k "旅行" -p 2 -s time_descending
  python cli_search.py -k "美食" -t _1 --time "一周内"
        '''
    )
    
    parser.add_argument('-k', '--keyword', required=True, help='搜索关键词')
    parser.add_argument('-p', '--page', type=int, default=1, help='页码 (默认：1)')
    parser.add_argument('-s', '--sort', default='collect_descending', 
                       choices=['general', 'popularity_descending', 'time_descending', 
                               'comment_descending', 'collect_descending'],
                       help='排序方式 (默认：collect_descending，支持翻页)')
    parser.add_argument('-t', '--type', default='_0', choices=['_0', '_1', '_2'],
                       help='笔记类型：_0=通用，_1=视频，_2=普通 (默认：_0)')
    parser.add_argument('--time', dest='note_time', 
                       choices=['一天内', '一周内', '半年内'],
                       help='时间筛选')
    parser.add_argument('--pages', type=int, default=1, help='采集页数（默认：1）')
    parser.add_argument('--delay', type=float, default=2.0, help='每页延迟时间（秒，默认：2.0）')
    parser.add_argument('--no-dedup', action='store_true', help='不去重（默认自动去重）')
    parser.add_argument('-o', '--output', help='输出文件路径（Excel 或 JSON 格式，根据扩展名自动判断）')
    
    args = parser.parse_args()
    
    # 加载 API Token
    api_token = load_api_token()
    
    # 初始化搜索器
    searcher = XHSNoteSearch(api_token)
    
    print(f"\n🔍 正在搜索 \"{args.keyword}\" ...")
    print(f"   排序：{args.sort}")
    print(f"   类型：{args.type}")
    if args.note_time:
        print(f"   时间：{args.note_time}")
    print(f"   采集页数：{args.pages}")
    print(f"   延迟：{args.delay}秒")
    print()
    
    # 执行搜索（多页采集）
    if args.pages > 1:
        result = searcher.search_all_pages(
            keyword=args.keyword,
            max_pages=args.pages,
            sort=args.sort,
            note_time=args.note_time,
            delay_seconds=args.delay,
            deduplicate=not args.no_dedup
        )
    else:
        result = searcher.search(
            keyword=args.keyword,
            page=args.page,
            sort=args.sort,
            note_type=args.type,
            note_time=args.note_time
        )
    
    # 输出结果
    print(searcher.format_results(result))
    
    # 保存到文件
    if result.get("success"):
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            # 默认保存到技能根目录
            output_dir = Path(__file__).parent
            output_path = output_dir / f"search_{args.keyword}_{args.sort}.xlsx"
        
        # 根据扩展名判断导出格式
        output_path = str(output_path)
        if output_path.endswith('.xlsx'):
            # 导出 Excel
            searcher.export_to_excel(result, output_path)
            print(f"\n✅ Excel 已保存到：{output_path}")
        else:
            # 导出 JSON
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(result.get("data", {}), f, ensure_ascii=False, indent=2)
                print(f"\n✅ JSON 已保存到：{output_path}")
            except Exception as e:
                print(f"\n❌ 保存失败：{e}")


if __name__ == "__main__":
    main()
