#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控下载进度和日志的脚本
"""

import os
import time
import glob

def check_logs():
    """查看日志文件"""
    print("=== 查看日志文件 ===")
    
    log_files = glob.glob("logs/*.log")
    if log_files:
        for log_file in log_files:
            print(f"\n--- {log_file} ---")
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 显示最后20行
                    for line in lines[-20:]:
                        print(line.strip())
            except Exception as e:
                print(f"读取日志失败: {e}")
    else:
        print("没有找到日志文件")

def check_downloads():
    """查看下载目录"""
    print("\n=== 查看下载目录 ===")
    
    downloads_dir = "downloads"
    if os.path.exists(downloads_dir):
        for root, dirs, files in os.walk(downloads_dir):
            if files:
                rel_path = os.path.relpath(root, downloads_dir)
                print(f"\n目录: {rel_path}")
                
                total_size = 0
                for file in files:
                    file_path = os.path.join(root, file)
                    size = os.path.getsize(file_path)
                    total_size += size
                    print(f"  {file} - {size} bytes ({size/1024:.1f} KB)")
                
                print(f"  总计: {len(files)} 个文件, {total_size/1024:.1f} KB")
    else:
        print("下载目录不存在")

def monitor_progress():
    """监控下载进度"""
    print("=== 开始监控下载进度 ===")
    print("每10秒检查一次，按Ctrl+C停止监控")
    
    try:
        while True:
            print(f"\n[{time.strftime('%H:%M:%S')}] 检查进度...")
            
            # 检查下载目录
            check_downloads()
            
            # 检查最新日志
            print("\n最新日志:")
            log_files = glob.glob("logs/*.log")
            if log_files:
                latest_log = max(log_files, key=os.path.getmtime)
                try:
                    with open(latest_log, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 显示最后5行
                        for line in lines[-5:]:
                            if any(keyword in line for keyword in ['下载', '解析', '错误', '完成']):
                                print(f"  {line.strip()}")
                except Exception:
                    pass
            
            print("-" * 50)
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n监控停止")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "logs":
            check_logs()
        elif sys.argv[1] == "downloads":
            check_downloads()
        elif sys.argv[1] == "monitor":
            monitor_progress()
        else:
            print("用法: python monitor.py [logs|downloads|monitor]")
    else:
        print("检查修复效果")
        print("=" * 40)
        check_logs()
        check_downloads()
        print("\n要持续监控请运行: python monitor.py monitor")