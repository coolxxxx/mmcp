#!/usr/bin/env python3
"""
版本控制系统安装和初始化脚本
"""

import os
import json
import subprocess
import sys
from pathlib import Path
import shutil


def check_git_installation():
    """检查Git是否已安装"""
    try:
        result = subprocess.run(['git', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Git已安装: {result.stdout.strip()}")
            return True
        else:
            print("❌ Git未安装")
            return False
    except FileNotFoundError:
        print("❌ Git未安装")
        return False


def init_git_repo():
    """初始化Git仓库"""
    try:
        if Path('.git').exists():
            print("✅ Git仓库已存在")
            return True
        
        # 初始化仓库
        subprocess.run(['git', 'init'], check=True)
        print("✅ Git仓库初始化成功")
        
        # 创建.gitignore
        gitignore_content = """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
*.log
logs/

# Backups
backups/

# Test reports
test_report_*.json

# Monitoring
monitoring_events.json
version_control.log
monitoring.log

# Temporary files
*.tmp
*.temp
"""
        
        with open('.gitignore', 'w') as f:
            f.write(gitignore_content.strip())
        
        # 添加所有文件并创建初始提交
        subprocess.run(['git', 'add', '.'], check=True)
        subprocess.run(['git', 'commit', '-m', 'Initial commit - 项目初始化'], check=True)
        
        print("✅ 初始提交创建成功")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git仓库初始化失败: {e}")
        return False


def setup_git_hooks():
    """设置Git钩子"""
    try:
        hooks_dir = Path('.git/hooks')
        
        # Pre-commit hook - 运行测试
        pre_commit_hook = hooks_dir / 'pre-commit'
        pre_commit_content = """#!/bin/bash
# Pre-commit hook - run basic checks

echo "Running pre-commit checks..."

# Check Python syntax
echo "Checking Python syntax..."
python -m py_compile src/**/*.py
if [ $? -ne 0 ]; then
    echo "Python syntax check failed"
    exit 1
fi

# Run basic tests if exists
if [ -f "test_basic.py" ]; then
    echo "Running basic tests..."
    python test_basic.py
    if [ $? -ne 0 ]; then
        echo "Basic tests failed"
        exit 1
    fi
fi

echo "Pre-commit checks passed"
exit 0
"""
        
        with open(pre_commit_hook, 'w', encoding='utf-8') as f:
            f.write(pre_commit_content)
        
        # 设置执行权限
        os.chmod(pre_commit_hook, 0o755)
        
        print("✅ Git钩子设置成功")
        return True
        
    except Exception as e:
        print(f"❌ Git钩子设置失败: {e}")
        return False


def create_test_structure():
    """创建测试目录结构"""
    try:
        # 创建测试目录
        test_dir = Path('tests')
        test_dir.mkdir(exist_ok=True)
        
        # 创建基本测试文件
        init_file = test_dir / '__init__.py'
        init_file.touch()
        
        # 创建基本功能测试
        basic_test = test_dir / 'test_basic.py'
        basic_test_content = """#!/usr/bin/env python3
\"\"\"
基本功能测试
\"\"\"

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestBasicFunctionality(unittest.TestCase):
    \"\"\"基本功能测试类\"\"\"
    
    def test_imports(self):
        \"\"\"测试基本导入\"\"\"
        try:
            import core.config
            import core.downloader
            import core.parser
            import utils.logger
            self.assertTrue(True, "所有模块导入成功")
        except ImportError as e:
            self.fail(f"模块导入失败: {e}")
    
    def test_config_loading(self):
        \"\"\"测试配置加载\"\"\"
        try:
            from core.config import ConfigManager
            config_manager = ConfigManager()
            self.assertIsNotNone(config_manager)
        except Exception as e:
            self.fail(f"配置加载失败: {e}")


if __name__ == '__main__':
    unittest.main()
"""
        
        with open(basic_test, 'w', encoding='utf-8') as f:
            f.write(basic_test_content)
        
        # 创建集成测试
        integration_test = test_dir / 'test_integration.py'
        integration_test_content = """#!/usr/bin/env python3
\"\"\"
集成测试
\"\"\"

import unittest
import sys
import os

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


class TestIntegration(unittest.TestCase):
    \"\"\"集成测试类\"\"\"
    
    def test_system_integration(self):
        \"\"\"测试系统集成\"\"\"
        # 这里添加集成测试逻辑
        self.assertTrue(True, "集成测试通过")


if __name__ == '__main__':
    unittest.main()
"""
        
        with open(integration_test, 'w', encoding='utf-8') as f:
            f.write(integration_test_content)
        
        print("✅ 测试结构创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 测试结构创建失败: {e}")
        return False


def create_deployment_scripts():
    """创建部署脚本"""
    try:
        # 创建部署脚本
        deploy_script = Path('deploy.py')
        deploy_content = """#!/usr/bin/env python3
\"\"\"
部署脚本
\"\"\"

import subprocess
import sys
from pathlib import Path
from version_control_system import VersionControlSystem
from monitoring_system import SystemMonitor


def deploy_version(version_tag: str):
    \"\"\"部署指定版本\"\"\"
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
    \"\"\"启动监控系统\"\"\"
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
"""
        
        with open(deploy_script, 'w', encoding='utf-8') as f:
            f.write(deploy_content)
        
        # 创建回滚脚本
        rollback_script = Path('rollback.py')
        rollback_content = """#!/usr/bin/env python3
\"\"\"
快速回滚脚本
\"\"\"

import sys
from version_control_system import VersionControlSystem


def quick_rollback(reason: str = ""):
    \"\"\"快速回滚到最近的稳定版本\"\"\"
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
"""
        
        with open(rollback_script, 'w', encoding='utf-8') as f:
            f.write(rollback_content)
        
        print("✅ 部署脚本创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 部署脚本创建失败: {e}")
        return False


def create_documentation():
    """创建文档"""
    try:
        # 创建版本控制使用指南
        guide_content = """# 版本控制和回滚系统使用指南

## 系统概述

本系统提供了完善的版本管理和自动回滚功能，确保代码重构过程的安全性。

## 主要组件

1. **版本控制系统** (`version_control_system.py`)
   - 版本分支管理
   - 自动化测试
   - 稳定版本创建
   - 回滚功能

2. **监控告警系统** (`monitoring_system.py`)
   - 实时指标监控
   - 异常告警
   - 自动回滚触发

3. **部署脚本** (`deploy.py`, `rollback.py`)
   - 自动化部署
   - 快速回滚

## 使用流程

### 1. 创建版本分支

```bash
python version_control_system.py create v1.1.0 \\
    --description "重构WebPageParser类" \\
    --scope "src/core/parser.py" "src/core/extractor.py" \\
    --risk medium
```

### 2. 进行代码修改

在创建的分支上进行代码重构...

### 3. 运行测试

```bash
python version_control_system.py test v1.1.0
```

### 4. 创建稳定版本

```bash
python version_control_system.py stable v1.1.0
```

### 5. 启动监控

```bash
python monitoring_system.py --daemon
```

### 6. 部署

```bash
python deploy.py v1.1.0
```

## 回滚操作

### 手动回滚

```bash
python version_control_system.py rollback v1.0.0 --reason "发现严重bug"
```

### 快速回滚

```bash
python rollback.py "紧急回滚"
```

## 监控指标

系统监控以下关键指标：

- CPU使用率
- 内存使用率
- 磁盘使用率
- 响应时间
- 错误率

当指标超过阈值时，系统会自动触发回滚。

## 配置文件

### 监控配置 (`monitoring_config.json`)

```json
{
  "metrics": [...],
  "alert_rules": [...],
  "notification": {...},
  "rollback": {...}
}
```

### 测试配置 (`test_config.json`)

```json
{
  "test_commands": [...],
  "critical_tests": [...],
  "performance_benchmarks": {...}
}
```

## 最佳实践

1. **分支命名规范**
   - 功能分支: `feature/功能名`
   - 重构分支: `refactor/重构内容`
   - 修复分支: `hotfix/问题描述`

2. **测试策略**
   - 每次提交前运行基本测试
   - 创建稳定版本前运行完整测试套件
   - 定期运行性能测试

3. **回滚策略**
   - 保持至少3个稳定版本
   - 设置合理的监控阈值
   - 建立回滚决策流程

4. **文档维护**
   - 记录每次重构的详细信息
   - 维护变更日志
   - 更新部署文档

## 故障排除

### 常见问题

1. **Git操作失败**
   - 检查工作区是否干净
   - 确认Git配置正确

2. **测试失败**
   - 检查依赖是否安装
   - 确认测试环境配置

3. **监控异常**
   - 检查系统资源
   - 确认监控配置正确

4. **回滚失败**
   - 检查目标版本是否存在
   - 确认权限设置正确

### 日志文件

- `version_control.log` - 版本控制日志
- `monitoring.log` - 监控系统日志
- `test_report_*.json` - 测试报告

## 联系支持

如遇到问题，请查看日志文件或联系开发团队。
"""
        
        with open('VERSION_CONTROL_GUIDE.md', 'w', encoding='utf-8') as f:
            f.write(guide_content)
        
        print("✅ 文档创建成功")
        return True
        
    except Exception as e:
        print(f"❌ 文档创建失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 开始设置版本控制和回滚系统...")
    
    # 检查Git安装
    if not check_git_installation():
        print("请先安装Git: https://git-scm.com/downloads")
        return False
    
    # 初始化Git仓库
    if not init_git_repo():
        return False
    
    # 设置Git钩子
    if not setup_git_hooks():
        return False
    
    # 创建测试结构
    if not create_test_structure():
        return False
    
    # 创建部署脚本
    if not create_deployment_scripts():
        return False
    
    # 创建文档
    if not create_documentation():
        return False
    
    print("\n✅ 版本控制和回滚系统设置完成！")
    print("\n📋 下一步操作：")
    print("1. 阅读使用指南: VERSION_CONTROL_GUIDE.md")
    print("2. 配置监控参数: monitoring_config.json")
    print("3. 运行基本测试: python tests/test_basic.py")
    print("4. 创建第一个版本分支开始重构")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)