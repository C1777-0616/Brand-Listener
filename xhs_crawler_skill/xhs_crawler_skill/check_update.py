#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
技能版本检测和自动升级工具
"""

import requests
import json
import hashlib
import sys
from pathlib import Path
from datetime import datetime


SKILL_DIR = Path(__file__).parent
VERSION_FILE = SKILL_DIR / ".version.json"
UPGRADE_URL = "http://skills.ainm.store/api/public/skills/xhs_crawler_skill/download"


def get_current_version():
    """获取当前技能版本"""
    skill_md = SKILL_DIR / "SKILL.md"
    
    if not skill_md.exists():
        return None
    
    with open(skill_md, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('version:'):
                version = line.split(':', 1)[1].strip().strip('"')
                return version
    
    return None


def get_local_version_info():
    """获取本地版本信息"""
    if VERSION_FILE.exists():
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def check_version_update():
    """检查是否有新版本"""
    try:
        print("🔍 正在检查技能更新...")
        
        # 获取远程版本信息
        response = requests.get(UPGRADE_URL, timeout=10)
        
        if response.status_code == 200:
            # 计算远程文件的 MD5
            remote_md5 = hashlib.md5(response.content).hexdigest()
            
            # 获取本地版本信息
            local_info = get_local_version_info()
            current_version = get_current_version()
            
            print(f"📊 当前版本：v{current_version}")
            
            # 检查是否需要更新
            if local_info:
                local_md5 = local_info.get("md5", "")
                if remote_md5 != local_md5:
                    print(f"✨ 发现新版本！")
                    return True, response.content, remote_md5
                else:
                    print(f"✅ 已是最新版本")
                    return False, None, None
            else:
                # 首次使用，不提示更新
                print(f"ℹ️  首次使用，跳过版本检查")
                return False, None, None
        else:
            print(f"⚠️  版本检查失败：HTTP {response.status_code}")
            return False, None, None
    
    except Exception as e:
        print(f"⚠️  版本检查异常：{e}")
        return False, None, None


def save_version_info(content, md5):
    """保存版本信息"""
    version_info = {
        "version": get_current_version(),
        "md5": md5,
        "update_time": datetime.now().isoformat(),
        "upgrade_url": UPGRADE_URL
    }
    
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(version_info, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 版本信息已保存")


def main():
    """主函数"""
    print("=" * 80)
    print("技能版本检查")
    print("=" * 80)
    
    has_update, content, md5 = check_version_update()
    
    if has_update and content:
        print("\n🔄 正在自动升级技能...")
        
        # 这里可以实现自动下载和替换逻辑
        # 目前先保存版本信息
        save_version_info(content, md5)
        
        print("\n💡 提示：检测到新版本，请手动下载更新")
        print(f"   下载地址：{UPGRADE_URL}")
    else:
        print("\n✅ 技能已是最新版本")


if __name__ == "__main__":
    main()
