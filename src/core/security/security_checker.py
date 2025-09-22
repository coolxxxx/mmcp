"""
安全检查器
提供全面的安全检查和漏洞扫描功能
"""

import os
import re
import hashlib
import subprocess
import json
from typing import Dict, List, Any, Optional, Set, Tuple
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import logging

from ..exceptions import SecurityError


class SecurityLevel(Enum):
    """安全级别"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SecurityIssue:
    """安全问题"""
    id: str
    title: str
    description: str
    level: SecurityLevel
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    code_snippet: Optional[str] = None
    recommendation: Optional[str] = None
    cwe_id: Optional[str] = None  # Common Weakness Enumeration ID


@dataclass
class SecurityReport:
    """安全报告"""
    scan_id: str
    timestamp: float
    target_path: str
    issues: List[SecurityIssue]
    summary: Dict[str, Any]
    scan_duration: float


class SecurityChecker:
    """安全检查器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._init_patterns()
    
    def _init_patterns(self):
        """初始化安全模式"""
        self.vulnerability_patterns = {
            'command_injection': [
                (r'subprocess\.call\([^)]*shell\s*=\s*True', 'subprocess调用使用shell=True', SecurityLevel.HIGH),
                (r'os\.system\s*\(', '使用os.system执行命令', SecurityLevel.HIGH),
                (r'os\.popen\s*\(', '使用os.popen执行命令', SecurityLevel.MEDIUM),
                (r'subprocess\.Popen\([^)]*shell\s*=\s*True', 'Popen调用使用shell=True', SecurityLevel.HIGH),
            ],
            'path_traversal': [
                (r'open\s*\([^)]*\.\./.*\)', '可能的路径遍历攻击', SecurityLevel.HIGH),
                (r'\.\./', '路径中包含../模式', SecurityLevel.MEDIUM),
                (r'%2e%2e%2f', 'URL编码的路径遍历', SecurityLevel.HIGH),
            ],
            'hardcoded_secrets': [
                (r'password\s*=\s*["\'][^"\']{8,}["\']', '硬编码密码', SecurityLevel.CRITICAL),
                (r'api_key\s*=\s*["\'][^"\']{16,}["\']', '硬编码API密钥', SecurityLevel.CRITICAL),
                (r'secret\s*=\s*["\'][^"\']{16,}["\']', '硬编码密钥', SecurityLevel.CRITICAL),
                (r'token\s*=\s*["\'][^"\']{16,}["\']', '硬编码令牌', SecurityLevel.CRITICAL),
            ],
            'sql_injection': [
                (r'execute\s*\([^)]*%.*%', '可能的SQL注入', SecurityLevel.HIGH),
                (r'query\s*\([^)]*\+.*\+', 'SQL查询字符串拼接', SecurityLevel.MEDIUM),
                (r'SELECT.*\+.*\+', 'SQL SELECT语句拼接', SecurityLevel.MEDIUM),
            ],
            'unsafe_deserialization': [
                (r'pickle\.loads?\s*\(', '不安全的pickle反序列化', SecurityLevel.HIGH),
                (r'eval\s*\(', '使用eval函数', SecurityLevel.CRITICAL),
                (r'exec\s*\(', '使用exec函数', SecurityLevel.CRITICAL),
            ],
            'weak_crypto': [
                (r'hashlib\.md5\s*\(', '使用弱加密算法MD5', SecurityLevel.MEDIUM),
                (r'hashlib\.sha1\s*\(', '使用弱加密算法SHA1', SecurityLevel.MEDIUM),
                (r'random\.random\s*\(', '使用不安全的随机数生成器', SecurityLevel.LOW),
            ],
            'file_permissions': [
                (r'chmod\s*\([^)]*777', '设置过于宽松的文件权限', SecurityLevel.HIGH),
                (r'os\.chmod\s*\([^)]*0o777', '设置过于宽松的文件权限', SecurityLevel.HIGH),
            ],
            'network_security': [
                (r'requests\.get\s*\([^)]*verify\s*=\s*False', '禁用SSL证书验证', SecurityLevel.HIGH),
                (r'urllib.*verify\s*=\s*False', '禁用SSL证书验证', SecurityLevel.HIGH),
                (r'ssl\._create_unverified_context', '创建未验证的SSL上下文', SecurityLevel.HIGH),
            ]
        }
        
        self.file_patterns = {
            'sensitive_files': [
                r'.*\.pem$',
                r'.*\.key$',
                r'.*\.p12$',
                r'.*\.pfx$',
                r'.*id_rsa.*',
                r'.*id_dsa.*',
                r'.*\.ssh.*',
                r'.*config$',
                r'.*\.env$',
                r'.*\.secret$'
            ],
            'backup_files': [
                r'.*\.bak$',
                r'.*\.backup$',
                r'.*\.old$',
                r'.*\.orig$',
                r'.*~$'
            ],
            'log_files': [
                r'.*\.log$',
                r'.*\.out$',
                r'.*\.err$'
            ]
        }
    
    def scan_directory(self, directory_path: str, recursive: bool = True) -> SecurityReport:
        """
        扫描目录中的安全问题
        
        Args:
            directory_path: 目录路径
            recursive: 是否递归扫描
            
        Returns:
            安全报告
        """
        import time
        start_time = time.time()
        scan_id = hashlib.md5(f"{directory_path}_{start_time}".encode()).hexdigest()[:8]
        
        issues = []
        
        try:
            path_obj = Path(directory_path)
            if not path_obj.exists():
                raise SecurityError(f"目录不存在: {directory_path}")
            
            # 扫描文件
            if recursive:
                files = list(path_obj.rglob('*.py'))
            else:
                files = list(path_obj.glob('*.py'))
            
            for file_path in files:
                file_issues = self._scan_file(file_path)
                issues.extend(file_issues)
            
            # 扫描敏感文件
            sensitive_issues = self._scan_sensitive_files(path_obj, recursive)
            issues.extend(sensitive_issues)
            
            # 生成摘要
            summary = self._generate_summary(issues)
            
            scan_duration = time.time() - start_time
            
            return SecurityReport(
                scan_id=scan_id,
                timestamp=start_time,
                target_path=directory_path,
                issues=issues,
                summary=summary,
                scan_duration=scan_duration
            )
            
        except Exception as e:
            self.logger.error(f"安全扫描失败: {e}")
            raise SecurityError(f"安全扫描失败: {e}")
    
    def _scan_file(self, file_path: Path) -> List[SecurityIssue]:
        """扫描单个文件"""
        issues = []
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
            
            # 检查各种漏洞模式
            for category, patterns in self.vulnerability_patterns.items():
                for pattern, description, level in patterns:
                    matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
                    
                    for match in matches:
                        line_number = content[:match.start()].count('\n') + 1
                        line_content = lines[line_number - 1] if line_number <= len(lines) else ""
                        
                        issue = SecurityIssue(
                            id=f"{category}_{hashlib.md5(f'{file_path}_{line_number}_{pattern}'.encode()).hexdigest()[:8]}",
                            title=f"{category.replace('_', ' ').title()}: {description}",
                            description=f"在文件 {file_path} 第 {line_number} 行发现 {description}",
                            level=level,
                            file_path=str(file_path),
                            line_number=line_number,
                            code_snippet=line_content.strip(),
                            recommendation=self._get_recommendation(category),
                            cwe_id=self._get_cwe_id(category)
                        )
                        issues.append(issue)
            
        except Exception as e:
            self.logger.warning(f"扫描文件失败 {file_path}: {e}")
        
        return issues
    
    def _scan_sensitive_files(self, directory: Path, recursive: bool) -> List[SecurityIssue]:
        """扫描敏感文件"""
        issues = []
        
        try:
            if recursive:
                all_files = list(directory.rglob('*'))
            else:
                all_files = list(directory.glob('*'))
            
            for file_path in all_files:
                if not file_path.is_file():
                    continue
                
                filename = file_path.name.lower()
                
                # 检查敏感文件
                for pattern in self.file_patterns['sensitive_files']:
                    if re.match(pattern, filename):
                        issue = SecurityIssue(
                            id=f"sensitive_file_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}",
                            title="敏感文件发现",
                            description=f"发现可能包含敏感信息的文件: {file_path}",
                            level=SecurityLevel.MEDIUM,
                            file_path=str(file_path),
                            recommendation="确保敏感文件不被意外提交到版本控制系统"
                        )
                        issues.append(issue)
                        break
                
                # 检查备份文件
                for pattern in self.file_patterns['backup_files']:
                    if re.match(pattern, filename):
                        issue = SecurityIssue(
                            id=f"backup_file_{hashlib.md5(str(file_path).encode()).hexdigest()[:8]}",
                            title="备份文件发现",
                            description=f"发现备份文件: {file_path}",
                            level=SecurityLevel.LOW,
                            file_path=str(file_path),
                            recommendation="删除不必要的备份文件"
                        )
                        issues.append(issue)
                        break
        
        except Exception as e:
            self.logger.warning(f"扫描敏感文件失败: {e}")
        
        return issues
    
    def _get_recommendation(self, category: str) -> str:
        """获取修复建议"""
        recommendations = {
            'command_injection': "使用参数化命令执行，避免shell=True，验证所有用户输入",
            'path_traversal': "使用os.path.abspath()和os.path.commonpath()验证路径，限制文件访问范围",
            'hardcoded_secrets': "将敏感信息存储在环境变量或安全的配置文件中",
            'sql_injection': "使用参数化查询或ORM，永远不要直接拼接SQL语句",
            'unsafe_deserialization': "避免使用pickle反序列化不可信数据，使用JSON等安全格式",
            'weak_crypto': "使用强加密算法如SHA-256或更高版本，使用secrets模块生成随机数",
            'file_permissions': "设置适当的文件权限，遵循最小权限原则",
            'network_security': "始终验证SSL证书，使用HTTPS进行敏感数据传输"
        }
        return recommendations.get(category, "请查阅相关安全最佳实践")
    
    def _get_cwe_id(self, category: str) -> str:
        """获取CWE ID"""
        cwe_mapping = {
            'command_injection': 'CWE-78',
            'path_traversal': 'CWE-22',
            'hardcoded_secrets': 'CWE-798',
            'sql_injection': 'CWE-89',
            'unsafe_deserialization': 'CWE-502',
            'weak_crypto': 'CWE-327',
            'file_permissions': 'CWE-732',
            'network_security': 'CWE-295'
        }
        return cwe_mapping.get(category, 'CWE-Unknown')
    
    def _generate_summary(self, issues: List[SecurityIssue]) -> Dict[str, Any]:
        """生成扫描摘要"""
        summary = {
            'total_issues': len(issues),
            'by_level': {level.value: 0 for level in SecurityLevel},
            'by_category': {},
            'critical_issues': 0,
            'high_issues': 0,
            'medium_issues': 0,
            'low_issues': 0
        }
        
        for issue in issues:
            # 按级别统计
            summary['by_level'][issue.level.value] += 1
            
            # 按类别统计
            category = issue.title.split(':')[0] if ':' in issue.title else 'Other'
            summary['by_category'][category] = summary['by_category'].get(category, 0) + 1
            
            # 简化统计
            if issue.level == SecurityLevel.CRITICAL:
                summary['critical_issues'] += 1
            elif issue.level == SecurityLevel.HIGH:
                summary['high_issues'] += 1
            elif issue.level == SecurityLevel.MEDIUM:
                summary['medium_issues'] += 1
            elif issue.level == SecurityLevel.LOW:
                summary['low_issues'] += 1
        
        return summary
    
    def export_report(self, report: SecurityReport, output_path: str, format: str = 'json'):
        """
        导出安全报告
        
        Args:
            report: 安全报告
            output_path: 输出路径
            format: 输出格式 (json, html, csv)
        """
        try:
            if format.lower() == 'json':
                self._export_json_report(report, output_path)
            elif format.lower() == 'html':
                self._export_html_report(report, output_path)
            elif format.lower() == 'csv':
                self._export_csv_report(report, output_path)
            else:
                raise ValueError(f"不支持的输出格式: {format}")
                
        except Exception as e:
            self.logger.error(f"导出报告失败: {e}")
            raise SecurityError(f"导出报告失败: {e}")
    
    def _export_json_report(self, report: SecurityReport, output_path: str):
        """导出JSON格式报告"""
        report_dict = {
            'scan_id': report.scan_id,
            'timestamp': report.timestamp,
            'target_path': report.target_path,
            'scan_duration': report.scan_duration,
            'summary': report.summary,
            'issues': [
                {
                    'id': issue.id,
                    'title': issue.title,
                    'description': issue.description,
                    'level': issue.level.value,
                    'file_path': issue.file_path,
                    'line_number': issue.line_number,
                    'code_snippet': issue.code_snippet,
                    'recommendation': issue.recommendation,
                    'cwe_id': issue.cwe_id
                }
                for issue in report.issues
            ]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
    
    def _export_html_report(self, report: SecurityReport, output_path: str):
        """导出HTML格式报告"""
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>安全扫描报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .header { background-color: #f0f0f0; padding: 20px; border-radius: 5px; }
        .summary { margin: 20px 0; }
        .issue { border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; }
        .critical { border-left: 5px solid #d32f2f; }
        .high { border-left: 5px solid #f57c00; }
        .medium { border-left: 5px solid #fbc02d; }
        .low { border-left: 5px solid #388e3c; }
        .code { background-color: #f5f5f5; padding: 10px; font-family: monospace; }
    </style>
</head>
<body>
    <div class="header">
        <h1>安全扫描报告</h1>
        <p>扫描ID: {scan_id}</p>
        <p>目标路径: {target_path}</p>
        <p>扫描时间: {scan_duration:.2f}秒</p>
    </div>
    
    <div class="summary">
        <h2>摘要</h2>
        <p>总问题数: {total_issues}</p>
        <p>严重: {critical_issues} | 高危: {high_issues} | 中危: {medium_issues} | 低危: {low_issues}</p>
    </div>
    
    <div class="issues">
        <h2>问题详情</h2>
        {issues_html}
    </div>
</body>
</html>
        """
        
        issues_html = ""
        for issue in report.issues:
            issue_html = f"""
            <div class="issue {issue.level.value}">
                <h3>{issue.title}</h3>
                <p>{issue.description}</p>
                {f'<p><strong>文件:</strong> {issue.file_path}:{issue.line_number}</p>' if issue.file_path else ''}
                {f'<div class="code">{issue.code_snippet}</div>' if issue.code_snippet else ''}
                {f'<p><strong>建议:</strong> {issue.recommendation}</p>' if issue.recommendation else ''}
                {f'<p><strong>CWE ID:</strong> {issue.cwe_id}</p>' if issue.cwe_id else ''}
            </div>
            """
            issues_html += issue_html
        
        html_content = html_template.format(
            scan_id=report.scan_id,
            target_path=report.target_path,
            scan_duration=report.scan_duration,
            total_issues=report.summary['total_issues'],
            critical_issues=report.summary['critical_issues'],
            high_issues=report.summary['high_issues'],
            medium_issues=report.summary['medium_issues'],
            low_issues=report.summary['low_issues'],
            issues_html=issues_html
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _export_csv_report(self, report: SecurityReport, output_path: str):
        """导出CSV格式报告"""
        import csv
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'ID', 'Title', 'Description', 'Level', 'File Path', 
                'Line Number', 'Code Snippet', 'Recommendation', 'CWE ID'
            ])
            
            for issue in report.issues:
                writer.writerow([
                    issue.id,
                    issue.title,
                    issue.description,
                    issue.level.value,
                    issue.file_path or '',
                    issue.line_number or '',
                    issue.code_snippet or '',
                    issue.recommendation or '',
                    issue.cwe_id or ''
                ])


# 便捷函数
def check_url_security(url: str) -> Dict[str, Any]:
    """检查URL安全性"""
    from .input_validator import validate_url, ValidationLevel
    return validate_url(url, ValidationLevel.STRICT)


def check_file_security(file_path: str) -> Dict[str, Any]:
    """检查文件安全性"""
    from .input_validator import validate_file_path, ValidationLevel
    return validate_file_path(file_path, ValidationLevel.STRICT)


def scan_for_vulnerabilities(directory_path: str) -> SecurityReport:
    """扫描漏洞的便捷函数"""
    checker = SecurityChecker()
    return checker.scan_directory(directory_path)