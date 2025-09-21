#!/usr/bin/env python3
"""
部署脚本
"""

import subprocess
import sys
from pathlib import Path
from version_control_system import VersionControlSystem
from monitoring_system import SystemMonitor


def deploy_version(version_tag: str):
    """部署指定版本"""
    print(f"开始部署版本: {version_tag}")
    
    vcs = VersionControlSystem()
    
    # 运行测试
    if not vcs.run_automated_tests(version_tag):
        print("❌ 测试失败，部署中止")
        return False
    
    # 创建稳定版本
    if not vcs.create_stable_version(version_tag):
        print("❌ 创建稳定版本失败")
        return False
    
    print("✅ 部署成功")
    return True


def start_monitoring():
    """启动监控系统"""
    print("启动监控系统...")
    monitor = SystemMonitor()
    monitor.start_monitoring()
    print("✅ 监控系统已启动")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python deploy.py <version_tag>")
        sys.exit(1)
    
    version_tag = sys.argv[1]
    
    if deploy_version(version_tag):
        start_monitoring()
    else:
        sys.exit(1)
