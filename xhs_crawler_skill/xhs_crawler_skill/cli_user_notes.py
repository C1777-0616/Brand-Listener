#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书用户笔记采集 CLI 工具
"""
import sys
import json
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from user_notes import XHSUserNotes


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
        description='小红书用户笔记采集工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python cli_user_notes.py -u 5b83d9b2bced640001784c33
  python cli_user_notes.py -u 5b83d9b2bced640001784c33 --all
  python cli_user_notes.py -u 5b83d9b2bced640001784c33 --all --pages 5
  python cli_user_notes.py -u 5b83d9b2bced640001784c33 -o user_notes.json

注意:
  博主主页笔记采集可能存在翻页限制，建议优先使用单页采集模式。
  如需采集多页，请增加延迟时间（--delay 30 以上）以提高成功率。
        '''
    )
    
    parser.add_argument('-u', '--user-id', required=True, help='用户 ID')
    parser.add_argument('--all', action='store_true', help='采集所有笔记（自动分页）')
    parser.add_argument('--pages', type=int, help='最大页数（仅在全量采集时有效）')
    parser.add_argument('--delay', type=float, default=30.0, help='每页延迟时间（秒，默认：30.0）')
    parser.add_argument('-o', '--output', help='输出文件路径（Excel 或 JSON 格式，根据扩展名自动判断）')
    
    args = parser.parse_args()
    
    # 加载 API Token
    api_token = load_api_token()
    
    # 初始化采集器
    crawler = XHSUserNotes(api_token)
    
    print(f"\n📥 正在采集用户 {args.user_id} 的笔记...")
    if args.all:
        print(f"   模式：全量采集")
        if args.pages:
            print(f"   最大页数：{args.pages}")
        print(f"   延迟：{args.delay}秒")
    else:
        print(f"   模式：单页采集")
    print()
    
    # 执行采集
    if args.all:
        result = crawler.get_all_user_notes(
            user_id=args.user_id,
            max_pages=args.pages,
            delay_seconds=args.delay
        )
    else:
        result = crawler.get_user_notes(user_id=args.user_id)
    
    # 输出结果
    print(crawler.format_notes(result))
    
    # 保存到文件
    if result.get("success"):
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            # 默认保存到技能根目录
            output_dir = Path(__file__).parent
            output_path = output_dir / f"user_notes_{args.user_id}.xlsx"
        
        # 根据扩展名判断导出格式
        output_path = str(output_path)
        if output_path.endswith('.xlsx'):
            # 导出 Excel
            notes = result.get("data", {}).get("notes", [])
            if crawler.export_to_excel(notes, output_path):
                print(f"\n✅ Excel 已保存到：{output_path}")
            else:
                print(f"\n❌ 导出失败")
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
