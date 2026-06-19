#!/usr/bin/env python3
"""
测试运行脚本
提供便捷的测试执行和报告生成功能
"""

import os
import sys
import subprocess
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

def run_pytest(args):
    """运行pytest测试"""
    cmd = [sys.executable, "-m", "pytest"]
    
    # 添加基本参数
    cmd.extend([
        "--verbose",
        "--tb=short",
    ])

    if args.coverage:
        cmd.extend([
            "--cov=src",
            "--cov-report=html:htmlcov",
            "--cov-report=term-missing",
            "--cov-report=xml",
        ])
    
    # 根据参数添加选项
    if args.fast:
        cmd.extend(["-x", "--disable-warnings"])
    
    if args.parallel:
        cmd.extend(["-n", "auto"])
    
    if args.markers:
        cmd.extend(["-m", args.markers])
    
    if args.coverage and args.coverage_fail_under is not None:
        cmd.extend([f"--cov-fail-under={args.coverage_fail_under}"])
    
    if args.test_path:
        cmd.append(args.test_path)
    else:
        cmd.append("tests/")
    
    print(f"运行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except Exception as e:
        print(f"测试运行失败: {e}")
        return 1

def run_specific_tests():
    """运行特定类型的测试"""
    test_categories = {
        "unit": "tests/",
        "download": "tests/test_download_manager.py",
        "security": "tests/test_input_validator.py",
        "legacy-concurrency": "test_concurrency_modules.py",
        "legacy-exceptions": "test_exception_system.py",
        "legacy-security": "test_security_system.py"
    }
    
    print("可用的测试类别:")
    for category, description in test_categories.items():
        print(f"  {category}: {description}")
    
    return test_categories

def generate_test_report():
    """生成测试报告"""
    report_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_summary": {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        },
        "coverage": {
            "total_coverage": 0,
            "line_coverage": 0,
            "branch_coverage": 0
        },
        "modules": []
    }
    
    # 检查是否存在覆盖率报告
    coverage_file = "coverage.xml"
    if os.path.exists(coverage_file):
        print(f"发现覆盖率报告: {coverage_file}")
        # 这里可以解析XML文件获取详细信息
    
    # 保存报告
    with open("test_report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    print("测试报告已生成: test_report.json")

def check_test_environment():
    """检查测试环境"""
    print("检查测试环境...")
    
    # 检查Python版本
    python_version = sys.version_info
    print(f"Python版本: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version < (3, 8):
        print("警告: Python版本过低，建议使用3.8+")
    
    # 检查必要的包
    required_packages = {
        "pytest": "pytest",
        "pytest-cov": "pytest_cov",
        "pytest-xdist": "xdist",
        "requests": "requests",
        "beautifulsoup4": "bs4",
        "Pillow": "PIL",
        "cryptography": "cryptography",
        "psutil": "psutil",
        "aiohttp": "aiohttp",
        "aiofiles": "aiofiles",
    }

    missing_packages = []
    for package, import_name in required_packages.items():
        try:
            __import__(import_name)
            print(f"[OK] {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"[MISSING] {package} (缺失)")

    if missing_packages:
        print(f"\n缺失的包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements-dev.txt")
        return False
    
    # 检查测试目录
    test_dir = Path("tests")
    if not test_dir.exists():
        print("[MISSING] tests目录不存在")
        return False

    test_files = list(test_dir.glob("test_*.py"))
    print(f"[OK] 发现 {len(test_files)} 个测试文件")
    
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="测试运行脚本")
    parser.add_argument("--fast", action="store_true", help="快速测试模式")
    parser.add_argument("--parallel", action="store_true", help="并行测试")
    parser.add_argument("--markers", help="运行特定标记的测试")
    parser.add_argument("--coverage", action="store_true", help="生成覆盖率报告")
    parser.add_argument("--coverage-fail-under", type=int, help="覆盖率阈值（需同时使用 --coverage）")
    parser.add_argument("--test-path", help="指定测试路径")
    parser.add_argument("--check-env", action="store_true", help="检查测试环境")
    parser.add_argument("--list-categories", action="store_true", help="列出测试类别")
    parser.add_argument("--generate-report", action="store_true", help="生成测试报告")
    
    args = parser.parse_args()
    
    if args.check_env:
        if not check_test_environment():
            return 1
        return 0
    
    if args.list_categories:
        run_specific_tests()
        return 0
    
    if args.generate_report:
        generate_test_report()
        return 0
    
    # 检查环境
    if not check_test_environment():
        print("环境检查失败，请先解决依赖问题")
        return 1
    
    # 运行测试
    return run_pytest(args)

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
