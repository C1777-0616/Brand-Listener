#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书分享链接转换 CLI 工具
支持单个链接转换和批量转换，可导出 Excel
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional


def load_api_token() -> Optional[str]:
    """从 .env 文件加载 API Token"""
    env_file = Path(__file__).parent / ".env"
    
    if not env_file.exists():
        return None
    
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('XHS_API_TOKEN='):
                return line.split('=', 1)[1].strip()
    
    return None


def load_urls_from_file(filepath: str) -> List[str]:
    """从文件加载 URL 列表（每行一个 URL）"""
    urls = []
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):  # 跳过空行和注释
                    urls.append(url)
    except Exception as e:
        print(f"❌ 读取文件失败：{e}")
        sys.exit(1)
    
    return urls


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="小红书分享链接转换工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换单个链接
  python cli_share_link.py -u "https://www.xiaohongshu.com/explore/xxx"
  
  # 批量转换（从文件读取 URL）
  python cli_share_link.py -f urls.txt
  
  # 批量转换并导出 Excel
  python cli_share_link.py -f urls.txt -o result.xlsx
  
  # 指定 API Token（不配置文件）
  python cli_share_link.py -u "xxx" -t sk-your-token-here
        """
    )
    
    # 输入参数
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '-u', '--url',
        help='单个分享链接'
    )
    input_group.add_argument(
        '-f', '--file',
        help='包含多个分享链接的文件（每行一个）'
    )
    
    # 其他参数
    parser.add_argument(
        '-t', '--token',
        help='API Token（不填则从 .env 文件读取）'
    )
    parser.add_argument(
        '-o', '--output',
        help='输出文件路径（Excel 格式，仅批量转换时有效）'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        help='每个链接之间的延迟时间（秒，默认：0.5）'
    )
    
    args = parser.parse_args()
    
    # 获取 API Token
    api_token = args.token or load_api_token()
    
    if not api_token:
        print("❌ 未提供 API Token！")
        print("   请使用 -t 参数指定，或在 .env 文件中配置 XHS_API_TOKEN")
        sys.exit(1)
    
    # 导入转换类
    from share_link_convert import XHSShareLinkConverter
    
    converter = XHSShareLinkConverter(api_token)
    
    # 处理单个链接
    if args.url:
        print("\n🔗 正在转换链接...")
        print(f"   原始链接：{args.url}")
        
        result = converter.convert_share_url(args.url)
        print(converter.format_result(result))
        
        if result.get("success"):
            note_id = result.get("data", {}).get("note_id", "")
            print(f"\n💡 提示：可以使用该笔记 ID 调用笔记详情或评论 API")
            print(f"   python cli_detail.py -n {note_id}")
            print(f"   python cli_comments.py -n {note_id} --all --sub-comments")
        else:
            sys.exit(1)
    
    # 批量转换
    elif args.file:
        print("\n📋 从文件加载链接...")
        urls = load_urls_from_file(args.file)
        
        if not urls:
            print("❌ 文件中没有有效的链接！")
            sys.exit(1)
        
        print(f"✅ 加载 {len(urls)} 个链接")
        
        print("\n🔄 开始批量转换...")
        print(f"   链接数量：{len(urls)}")
        print(f"   延迟时间：{args.delay}秒")
        
        if args.output:
            print(f"   导出路径：{args.output}")
        
        # 执行批量转换
        batch_result = converter.convert_batch(urls, delay_seconds=args.delay)
        
        # 输出统计
        data = batch_result.get("data", {})
        print("\n" + "=" * 80)
        print("批量转换完成")
        print("=" * 80)
        print(f"总计：{data.get('total', 0)} 个")
        print(f"成功：{data.get('success_count', 0)} 个")
        print(f"失败：{data.get('failed_count', 0)} 个")
        
        # 导出 Excel
        if args.output:
            print(f"\n📊 正在导出 Excel...")
            if converter.export_to_excel(batch_result, args.output):
                print(f"✅ Excel 已保存到：{args.output}")
            else:
                print(f"❌ 导出失败")
        else:
            # 如果没有指定输出路径，输出成功链接的笔记 ID
            print("\n转换成功的链接：")
            for item in data.get("results", []):
                if item.get("result", {}).get("success"):
                    note_id = item.get("result", {}).get("data", {}).get("note_id", "")
                    original_url = item.get("original_url", "")
                    print(f"   ✅ {original_url[:50]}... -> {note_id}")


if __name__ == "__main__":
    main()
