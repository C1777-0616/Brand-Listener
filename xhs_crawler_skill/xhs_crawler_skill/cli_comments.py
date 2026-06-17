#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书评论采集 CLI 工具
"""
import sys
import json
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from note_comments import XHSNoteComments


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
        description='小红书笔记评论采集工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python cli_comments.py -n 698af6400000000015031456
  python cli_comments.py -n 698af6400000000015031456 --all
  python cli_comments.py -n 698af6400000000015031456 --sub-comments
  python cli_comments.py -n 698af6400000000015031456 --all --sub-comments -o comments.xlsx
        '''
    )
    
    parser.add_argument('-n', '--note-id', required=True, help='笔记 ID')
    parser.add_argument('--all', action='store_true', help='采集所有评论（自动分页）')
    parser.add_argument('--pages', type=int, help='最大页数（仅在全量采集时有效）')
    parser.add_argument('--sub-comments', action='store_true', help='采集子评论（回复）')
    parser.add_argument('--sort', default='latest', choices=['latest', 'normal'],
                       help='排序方式：latest=最新，normal=默认 (默认：latest)')
    parser.add_argument('--delay', type=float, default=2.0, 
                       help='主评论分页延迟（秒，默认：2.0）')
    parser.add_argument('--sub-delay', type=float, default=1.0,
                       help='子评论采集延迟（秒，默认：1.0）')
    parser.add_argument('-o', '--output', help='输出文件路径 (Excel 格式)')
    
    args = parser.parse_args()
    
    # 加载 API Token
    api_token = load_api_token()
    
    # 初始化采集器
    crawler = XHSNoteComments(api_token)
    
    print(f"\n💬 正在采集笔记 {args.note_id} 的评论...")
    if args.all:
        print(f"   模式：全量采集")
        if args.pages:
            print(f"   最大页数：{args.pages}")
    else:
        print(f"   模式：单页采集")
    
    if args.sub_comments:
        print(f"   子评论：启用")
        print(f"   主评论延迟：{args.delay}秒")
        print(f"   子评论延迟：{args.sub_delay}秒")
    
    print(f"   排序：{args.sort}")
    print()
    
    # 执行采集
    if args.all:
        result = crawler.get_all_comments(
            note_id=args.note_id,
            max_pages=args.pages,
            delay_seconds=args.delay,
            sort=args.sort,
            fetch_sub_comments=args.sub_comments,
            sub_comment_delay=args.sub_delay
        )
    else:
        result = crawler.get_comments(
            note_id=args.note_id,
            sort=args.sort
        )
    
    # 输出结果
    if result.get("success"):
        data = result.get("data", {})
        comments = data.get("comments", [])
        comment_count = data.get("comment_count", 0)
        
        print(f"✅ 采集成功！")
        print(f"   主评论：{len(comments)} 条")
        
        if args.sub_comments:
            total_sub = sum(len(c.get("sub_comments", [])) for c in comments)
            print(f"   子评论：{total_sub} 条")
            print(f"   总计：{len(comments) + total_sub} 条")
        
        print(f"   API 参考总数：{comment_count} 条")
        
        # 导出 Excel
        if args.output:
            output_path = args.output
        else:
            # 默认保存到技能根目录
            output_dir = Path(__file__).parent
            output_path = output_dir / f"comments_{args.note_id}.xlsx"
        
        print(f"\n📊 正在导出 Excel...")
        if crawler.export_to_excel(result, str(output_path)):
            print(f"✅ Excel 已保存到：{output_path}")
        else:
            print(f"❌ 导出失败")
    else:
        print(f"❌ 采集失败：{result.get('message')}")


if __name__ == "__main__":
    main()
