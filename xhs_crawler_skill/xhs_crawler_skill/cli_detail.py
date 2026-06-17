#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小红书笔记详情采集 CLI 工具
"""
import sys
import json
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from note_detail import XHSNoteDetail


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
        description='小红书笔记详情采集工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
示例:
  python cli_detail.py -n 698af6400000000015031456
  python cli_detail.py -n 698af6400000000015031456 -o note_detail.json
  python cli_detail.py -n 698af6400000000015031456,69c260a90000000021010226

说明:
  - 不指定 -o 参数时，默认导出 Excel 到技能根目录
  - 指定 -o 参数时，根据扩展名导出为 Excel (.xlsx) 或 JSON (.json)
        '''
    )
    
    parser.add_argument('-n', '--note-ids', required=True, 
                       help='笔记 ID（多个用逗号分隔）')
    parser.add_argument('-o', '--output', help='输出文件路径（Excel 或 JSON 格式，根据扩展名自动判断）')
    
    args = parser.parse_args()
    
    # 解析笔记 ID 列表
    note_ids = [nid.strip() for nid in args.note_ids.split(',') if nid.strip()]
    
    if not note_ids:
        print("❌ 至少需要一个笔记 ID")
        sys.exit(1)
    
    # 加载 API Token
    api_token = load_api_token()
    
    # 初始化采集器
    crawler = XHSNoteDetail(api_token)
    
    print(f"\n📝 正在获取笔记详情...")
    print(f"   笔记数量：{len(note_ids)}")
    print()
    
    # 执行采集
    if len(note_ids) == 1:
        result = crawler.get_note_detail(note_ids[0])
        print(crawler.format_note_detail(result))
    else:
        # 批量采集
        result = crawler.get_notes_by_ids(note_ids, delay_seconds=1.0)
        
        if result.get("success"):
            notes = result.get("data", {}).get("notes", [])
            print(f"✅ 成功获取 {len(notes)}/{len(note_ids)} 条笔记\n")
            
            for i, note in enumerate(notes, 1):
                temp_result = {"success": True, "data": {"note": note}}
                print(crawler.format_note_detail(temp_result))
    
    # 保存到文件
    if result.get("success"):
        # 确定输出路径
        if args.output:
            output_path = args.output
        else:
            # 默认保存到技能根目录
            output_dir = Path(__file__).parent
            if len(note_ids) == 1:
                output_path = output_dir / f"note_{note_ids[0]}_detail.xlsx"
            else:
                output_path = output_dir / f"notes_detail_{len(note_ids)}.xlsx"
        
        # 根据扩展名判断导出格式
        output_path = str(output_path)
        if output_path.endswith('.xlsx'):
            # 导出 Excel
            if len(note_ids) == 1:
                notes = [result.get("data", {}).get("note", {})]
            else:
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
