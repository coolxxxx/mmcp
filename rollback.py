#!/usr/bin/env python3
"""
快速回滚脚本
"""

import sys
from version_control_system import VersionControlSystem


def quick_rollback(reason: str = ""):
    """快速回滚到最近的稳定版本"""
    vcs = VersionControlSystem()
    
    # 获取最近的稳定版本
    stable_versions = vcs.get_stable_versions(limit=1)
    
    if not stable_versions:
        print("❌ 没有可用的稳定版本")
        return False
    
    target_version = stable_versions[0].tag
    print(f"回滚到版本: {target_version}")
    
    success = vcs.rollback_to_version(target_version, reason)
    
    if success:
        print("✅ 回滚成功")
    else:
        print("❌ 回滚失败")
    
    return success


if __name__ == "__main__":
    reason = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "手动回滚"
    quick_rollback(reason)
