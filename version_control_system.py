#!/usr/bin/env python3
"""
版本管理和回滚系统
用于大型代码重构的安全保障
"""

import os
import json
import subprocess
import datetime
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import shutil
import hashlib


@dataclass
class VersionInfo:
    """版本信息数据类"""
    tag: str
    branch: str
    commit_hash: str
    timestamp: str
    description: str
    test_status: str  # passed, failed, pending
    rollback_priority: int  # 1-5, 1为最高优先级
    change_scope: List[str]  # 修改范围
    risk_level: str  # low, medium, high
    author: str


@dataclass
class RollbackRecord:
    """回滚记录数据类"""
    rollback_id: str
    from_version: str
    to_version: str
    timestamp: str
    reason: str
    success: bool
    duration_seconds: float


class VersionControlSystem:
    """版本控制和回滚系统"""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.versions_file = self.project_root / "version_history.json"
        self.rollback_log = self.project_root / "rollback_history.json"
        self.backup_dir = self.project_root / "backups"
        self.test_config = self.project_root / "test_config.json"
        
        # 创建必要的目录
        self.backup_dir.mkdir(exist_ok=True)
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('version_control.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化版本历史
        self._init_version_history()
        self._init_test_config()
    
    def _init_version_history(self):
        """初始化版本历史文件"""
        if not self.versions_file.exists():
            initial_data = {
                "versions": [],
                "current_version": None,
                "stable_versions": []
            }
            with open(self.versions_file, 'w', encoding='utf-8') as f:
                json.dump(initial_data, f, indent=2, ensure_ascii=False)
    
    def _init_test_config(self):
        """初始化测试配置"""
        if not self.test_config.exists():
            test_config = {
                "test_commands": [
                    "python -m pytest tests/ -v",
                    "python -m flake8 src/",
                    "python -m mypy src/",
                    "python -c 'import src.core.parser; print(\"Import test passed\")'"
                ],
                "critical_tests": [
                    "tests/test_core_functionality.py",
                    "tests/test_integration.py"
                ],
                "performance_benchmarks": {
                    "max_memory_mb": 500,
                    "max_cpu_percent": 80,
                    "max_response_time_ms": 1000
                }
            }
            with open(self.test_config, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2, ensure_ascii=False)
    
    def create_version_branch(self, version_name: str, description: str, 
                            change_scope: List[str], risk_level: str = "medium") -> bool:
        """创建版本分支"""
        try:
            # 检查Git仓库状态
            if not self._is_git_repo():
                self.logger.error("当前目录不是Git仓库")
                return False
            
            # 确保工作区干净
            if not self._is_working_directory_clean():
                self.logger.error("工作区有未提交的更改，请先提交或暂存")
                return False
            
            # 创建分支
            branch_name = f"refactor/{version_name}"
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name],
                capture_output=True, text=True, cwd=self.project_root
            )
            
            if result.returncode != 0:
                self.logger.error(f"创建分支失败: {result.stderr}")
                return False
            
            # 创建备份
            backup_path = self._create_backup(version_name)
            
            # 记录版本信息
            version_info = VersionInfo(
                tag=version_name,
                branch=branch_name,
                commit_hash=self._get_current_commit_hash(),
                timestamp=datetime.datetime.now().isoformat(),
                description=description,
                test_status="pending",
                rollback_priority=3,  # 默认中等优先级
                change_scope=change_scope,
                risk_level=risk_level,
                author=self._get_git_user()
            )
            
            self._save_version_info(version_info)
            self.logger.info(f"成功创建版本分支: {branch_name}")
            self.logger.info(f"备份路径: {backup_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"创建版本分支失败: {str(e)}")
            return False
    
    def run_automated_tests(self, version_tag: str) -> bool:
        """运行自动化测试"""
        try:
            self.logger.info(f"开始运行版本 {version_tag} 的自动化测试")
            
            # 加载测试配置
            with open(self.test_config, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            test_results = []
            all_passed = True
            
            # 运行测试命令
            for cmd in config["test_commands"]:
                self.logger.info(f"执行测试命令: {cmd}")
                result = subprocess.run(
                    cmd.split(), 
                    capture_output=True, 
                    text=True, 
                    cwd=self.project_root
                )
                
                test_result = {
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "passed": result.returncode == 0
                }
                
                test_results.append(test_result)
                if result.returncode != 0:
                    all_passed = False
                    self.logger.error(f"测试失败: {cmd}")
                    self.logger.error(f"错误输出: {result.stderr}")
            
            # 更新版本测试状态
            self._update_version_test_status(
                version_tag, 
                "passed" if all_passed else "failed",
                test_results
            )
            
            # 保存测试报告
            self._save_test_report(version_tag, test_results)
            
            return all_passed
            
        except Exception as e:
            self.logger.error(f"运行测试失败: {str(e)}")
            return False
    
    def create_stable_version(self, version_tag: str) -> bool:
        """创建稳定版本标签"""
        try:
            if not self.run_automated_tests(version_tag):
                self.logger.error("测试未通过，无法创建稳定版本")
                return False
            
            # 创建Git标签
            tag_name = f"stable-{version_tag}"
            result = subprocess.run(
                ["git", "tag", "-a", tag_name, "-m", f"Stable version {version_tag}"],
                capture_output=True, text=True, cwd=self.project_root
            )
            
            if result.returncode != 0:
                self.logger.error(f"创建标签失败: {result.stderr}")
                return False
            
            # 更新稳定版本列表
            self._add_stable_version(version_tag)
            
            self.logger.info(f"成功创建稳定版本: {tag_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"创建稳定版本失败: {str(e)}")
            return False
    
    def rollback_to_version(self, target_version: str, reason: str = "") -> bool:
        """回滚到指定版本"""
        try:
            rollback_id = self._generate_rollback_id()
            start_time = datetime.datetime.now()
            current_version = self._get_current_version()
            
            self.logger.info(f"开始回滚: {current_version} -> {target_version}")
            self.logger.info(f"回滚原因: {reason}")
            
            # 检查目标版本是否存在
            if not self._version_exists(target_version):
                self.logger.error(f"目标版本不存在: {target_version}")
                return False
            
            # 创建当前状态备份
            backup_path = self._create_backup(f"pre-rollback-{rollback_id}")
            
            # 执行回滚
            success = self._execute_rollback(target_version)
            
            # 记录回滚
            duration = (datetime.datetime.now() - start_time).total_seconds()
            rollback_record = RollbackRecord(
                rollback_id=rollback_id,
                from_version=current_version or "unknown",
                to_version=target_version,
                timestamp=start_time.isoformat(),
                reason=reason,
                success=success,
                duration_seconds=duration
            )
            
            self._save_rollback_record(rollback_record)
            
            if success:
                self.logger.info(f"回滚成功，耗时: {duration:.2f}秒")
                # 运行回滚后测试
                self.run_automated_tests(target_version)
            else:
                self.logger.error("回滚失败")
            
            return success
            
        except Exception as e:
            self.logger.error(f"回滚过程出错: {str(e)}")
            return False
    
    def get_stable_versions(self, limit: int = 3) -> List[VersionInfo]:
        """获取最近的稳定版本"""
        try:
            with open(self.versions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            stable_versions = []
            for version_data in data["versions"]:
                if version_data["tag"] in data["stable_versions"]:
                    stable_versions.append(VersionInfo(**version_data))
            
            # 按时间戳排序，返回最新的几个版本
            stable_versions.sort(key=lambda x: x.timestamp, reverse=True)
            return stable_versions[:limit]
            
        except Exception as e:
            self.logger.error(f"获取稳定版本失败: {str(e)}")
            return []
    
    def get_rollback_history(self, limit: int = 10) -> List[RollbackRecord]:
        """获取回滚历史"""
        try:
            if not self.rollback_log.exists():
                return []
            
            with open(self.rollback_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            records = [RollbackRecord(**record) for record in data["rollbacks"]]
            records.sort(key=lambda x: x.timestamp, reverse=True)
            return records[:limit]
            
        except Exception as e:
            self.logger.error(f"获取回滚历史失败: {str(e)}")
            return []
    
    def generate_change_log(self, from_version: str, to_version: str) -> str:
        """生成变更日志"""
        try:
            # 获取Git提交历史
            result = subprocess.run([
                "git", "log", f"{from_version}..{to_version}", 
                "--oneline", "--no-merges"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode != 0:
                return f"无法生成变更日志: {result.stderr}"
            
            commits = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            # 获取文件变更统计
            stat_result = subprocess.run([
                "git", "diff", "--stat", from_version, to_version
            ], capture_output=True, text=True, cwd=self.project_root)
            
            change_log = f"""
# 变更日志

**版本范围**: {from_version} -> {to_version}
**生成时间**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 提交记录 ({len(commits)} 个提交)

"""
            for commit in commits:
                if commit.strip():
                    change_log += f"- {commit}\n"
            
            change_log += f"""
## 文件变更统计

```
{stat_result.stdout}
```

## 风险评估

请在部署前仔细检查以下内容：
- [ ] 所有测试用例通过
- [ ] 关键功能验证完成
- [ ] 性能指标符合预期
- [ ] 安全检查通过
- [ ] 文档更新完成
"""
            
            return change_log
            
        except Exception as e:
            return f"生成变更日志失败: {str(e)}"
    
    # 私有方法
    def _is_git_repo(self) -> bool:
        """检查是否为Git仓库"""
        return (self.project_root / ".git").exists()
    
    def _is_working_directory_clean(self) -> bool:
        """检查工作区是否干净"""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=self.project_root
        )
        return result.returncode == 0 and not result.stdout.strip()
    
    def _get_current_commit_hash(self) -> str:
        """获取当前提交哈希"""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=self.project_root
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    
    def _get_git_user(self) -> str:
        """获取Git用户信息"""
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True, text=True, cwd=self.project_root
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    
    def _create_backup(self, version_name: str) -> str:
        """创建代码备份"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{version_name}_{timestamp}"
        backup_path = self.backup_dir / backup_name
        
        # 复制源代码目录
        shutil.copytree(
            self.project_root / "src",
            backup_path / "src",
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc')
        )
        
        # 复制重要配置文件
        important_files = ["config.json", "requirements.txt", "main.py"]
        for file_name in important_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                shutil.copy2(file_path, backup_path / file_name)
        
        return str(backup_path)
    
    def _save_version_info(self, version_info: VersionInfo):
        """保存版本信息"""
        with open(self.versions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data["versions"].append(asdict(version_info))
        data["current_version"] = version_info.tag
        
        with open(self.versions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _update_version_test_status(self, version_tag: str, status: str, results: List):
        """更新版本测试状态"""
        with open(self.versions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        for version in data["versions"]:
            if version["tag"] == version_tag:
                version["test_status"] = status
                break
        
        with open(self.versions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _save_test_report(self, version_tag: str, results: List):
        """保存测试报告"""
        report_path = self.project_root / f"test_report_{version_tag}.json"
        report_data = {
            "version": version_tag,
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results,
            "summary": {
                "total_tests": len(results),
                "passed": sum(1 for r in results if r["passed"]),
                "failed": sum(1 for r in results if not r["passed"])
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    def _add_stable_version(self, version_tag: str):
        """添加到稳定版本列表"""
        with open(self.versions_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if version_tag not in data["stable_versions"]:
            data["stable_versions"].append(version_tag)
            # 只保留最近的5个稳定版本
            data["stable_versions"] = data["stable_versions"][-5:]
        
        with open(self.versions_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _generate_rollback_id(self) -> str:
        """生成回滚ID"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        random_str = hashlib.md5(str(datetime.datetime.now()).encode()).hexdigest()[:8]
        return f"rollback_{timestamp}_{random_str}"
    
    def _get_current_version(self) -> Optional[str]:
        """获取当前版本"""
        try:
            with open(self.versions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("current_version")
        except:
            return None
    
    def _version_exists(self, version_tag: str) -> bool:
        """检查版本是否存在"""
        try:
            with open(self.versions_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return any(v["tag"] == version_tag for v in data["versions"])
        except:
            return False
    
    def _execute_rollback(self, target_version: str) -> bool:
        """执行实际的回滚操作"""
        try:
            # 切换到目标版本的标签或分支
            result = subprocess.run(
                ["git", "checkout", f"stable-{target_version}"],
                capture_output=True, text=True, cwd=self.project_root
            )
            
            if result.returncode != 0:
                # 尝试切换到分支
                result = subprocess.run(
                    ["git", "checkout", f"refactor/{target_version}"],
                    capture_output=True, text=True, cwd=self.project_root
                )
            
            return result.returncode == 0
            
        except Exception as e:
            self.logger.error(f"执行回滚失败: {str(e)}")
            return False
    
    def _save_rollback_record(self, record: RollbackRecord):
        """保存回滚记录"""
        if not self.rollback_log.exists():
            data = {"rollbacks": []}
        else:
            with open(self.rollback_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
        
        data["rollbacks"].append(asdict(record))
        
        with open(self.rollback_log, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """主函数 - 命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="版本管理和回滚系统")
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建版本分支
    create_parser = subparsers.add_parser('create', help='创建版本分支')
    create_parser.add_argument('version', help='版本名称')
    create_parser.add_argument('--description', required=True, help='版本描述')
    create_parser.add_argument('--scope', nargs='+', required=True, help='修改范围')
    create_parser.add_argument('--risk', choices=['low', 'medium', 'high'], 
                              default='medium', help='风险级别')
    
    # 运行测试
    test_parser = subparsers.add_parser('test', help='运行自动化测试')
    test_parser.add_argument('version', help='版本名称')
    
    # 创建稳定版本
    stable_parser = subparsers.add_parser('stable', help='创建稳定版本')
    stable_parser.add_argument('version', help='版本名称')
    
    # 回滚
    rollback_parser = subparsers.add_parser('rollback', help='回滚到指定版本')
    rollback_parser.add_argument('version', help='目标版本')
    rollback_parser.add_argument('--reason', default='', help='回滚原因')
    
    # 查看稳定版本
    list_parser = subparsers.add_parser('list', help='查看稳定版本')
    
    # 生成变更日志
    changelog_parser = subparsers.add_parser('changelog', help='生成变更日志')
    changelog_parser.add_argument('from_version', help='起始版本')
    changelog_parser.add_argument('to_version', help='目标版本')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    vcs = VersionControlSystem()
    
    if args.command == 'create':
        success = vcs.create_version_branch(
            args.version, args.description, args.scope, args.risk
        )
        print(f"创建版本分支: {'成功' if success else '失败'}")
    
    elif args.command == 'test':
        success = vcs.run_automated_tests(args.version)
        print(f"测试结果: {'通过' if success else '失败'}")
    
    elif args.command == 'stable':
        success = vcs.create_stable_version(args.version)
        print(f"创建稳定版本: {'成功' if success else '失败'}")
    
    elif args.command == 'rollback':
        success = vcs.rollback_to_version(args.version, args.reason)
        print(f"回滚操作: {'成功' if success else '失败'}")
    
    elif args.command == 'list':
        versions = vcs.get_stable_versions()
        print("稳定版本列表:")
        for v in versions:
            print(f"  {v.tag} - {v.description} ({v.timestamp})")
    
    elif args.command == 'changelog':
        changelog = vcs.generate_change_log(args.from_version, args.to_version)
        print(changelog)


if __name__ == "__main__":
    main()