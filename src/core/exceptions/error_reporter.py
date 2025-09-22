"""
错误报告器
提供错误收集、分析和报告功能
"""

import json
import time
import threading
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

from .base_exceptions import BaseApplicationException
from .error_handler import ErrorContext


class ReportLevel(Enum):
    """报告级别"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ErrorReport:
    """错误报告"""
    id: str
    timestamp: float
    level: ReportLevel
    exception_type: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    traceback: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'level': self.level.value,
            'exception_type': self.exception_type,
            'message': self.message,
            'context': self.context,
            'traceback': self.traceback,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'additional_data': self.additional_data
        }
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class ErrorReporter:
    """错误报告器"""
    
    def __init__(self, report_file: Optional[str] = None, max_reports: int = 10000):
        """
        初始化错误报告器
        
        Args:
            report_file: 报告文件路径
            max_reports: 最大报告数量
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.report_file = report_file
        self.max_reports = max_reports
        
        # 报告存储
        self.reports: List[ErrorReport] = []
        self.report_counter = 0
        
        # 报告回调
        self.report_callbacks: List[Callable[[ErrorReport], None]] = []
        
        # 过滤器
        self.filters: List[Callable[[ErrorReport], bool]] = []
        
        # 统计信息
        self.stats = {
            'total_reports': 0,
            'reports_by_level': {level.value: 0 for level in ReportLevel},
            'reports_by_type': {},
            'last_report_time': None
        }
        
        # 线程安全锁
        self.lock = threading.RLock()
        
        self.logger.info(f"错误报告器初始化完成，报告文件: {report_file}")
    
    def add_filter(self, filter_func: Callable[[ErrorReport], bool]):
        """
        添加报告过滤器
        
        Args:
            filter_func: 过滤函数，返回True表示保留报告
        """
        self.filters.append(filter_func)
        self.logger.debug("添加报告过滤器")
    
    def add_callback(self, callback: Callable[[ErrorReport], None]):
        """
        添加报告回调
        
        Args:
            callback: 回调函数
        """
        self.report_callbacks.append(callback)
        self.logger.debug("添加报告回调")
    
    def report_exception(self, exception: Exception, context: ErrorContext = None,
                        level: ReportLevel = None, additional_data: Dict[str, Any] = None) -> str:
        """
        报告异常
        
        Args:
            exception: 异常对象
            context: 错误上下文
            level: 报告级别
            additional_data: 附加数据
            
        Returns:
            报告ID
        """
        # 生成报告ID
        with self.lock:
            self.report_counter += 1
            report_id = f"ERR_{int(time.time())}_{self.report_counter:06d}"
        
        # 确定报告级别
        if level is None:
            level = self._determine_level(exception)
        
        # 创建报告
        report = ErrorReport(
            id=report_id,
            timestamp=time.time(),
            level=level,
            exception_type=type(exception).__name__,
            message=str(exception),
            context=context.to_dict() if context else {},
            traceback=self._get_traceback(exception),
            user_id=context.user_id if context else None,
            session_id=context.session_id if context else None,
            additional_data=additional_data or {}
        )
        
        # 应用过滤器
        if not self._should_report(report):
            return report_id
        
        # 存储报告
        self._store_report(report)
        
        # 触发回调
        self._trigger_callbacks(report)
        
        # 写入文件
        if self.report_file:
            self._write_to_file(report)
        
        self.logger.debug(f"生成错误报告: {report_id}")
        return report_id
    
    def report_message(self, message: str, level: ReportLevel = ReportLevel.INFO,
                      context: ErrorContext = None, additional_data: Dict[str, Any] = None) -> str:
        """
        报告消息
        
        Args:
            message: 消息内容
            level: 报告级别
            context: 错误上下文
            additional_data: 附加数据
            
        Returns:
            报告ID
        """
        # 生成报告ID
        with self.lock:
            self.report_counter += 1
            report_id = f"MSG_{int(time.time())}_{self.report_counter:06d}"
        
        # 创建报告
        report = ErrorReport(
            id=report_id,
            timestamp=time.time(),
            level=level,
            exception_type="Message",
            message=message,
            context=context.to_dict() if context else {},
            user_id=context.user_id if context else None,
            session_id=context.session_id if context else None,
            additional_data=additional_data or {}
        )
        
        # 应用过滤器
        if not self._should_report(report):
            return report_id
        
        # 存储报告
        self._store_report(report)
        
        # 触发回调
        self._trigger_callbacks(report)
        
        # 写入文件
        if self.report_file:
            self._write_to_file(report)
        
        return report_id
    
    def _determine_level(self, exception: Exception) -> ReportLevel:
        """确定报告级别"""
        if isinstance(exception, (SystemExit, KeyboardInterrupt, MemoryError)):
            return ReportLevel.CRITICAL
        elif isinstance(exception, (ConnectionError, TimeoutError, OSError)):
            return ReportLevel.ERROR
        elif isinstance(exception, (ValueError, TypeError, AttributeError)):
            return ReportLevel.WARNING
        elif isinstance(exception, BaseApplicationException):
            # 根据应用异常的严重程度确定级别
            if hasattr(exception, 'severity'):
                severity_mapping = {
                    'critical': ReportLevel.CRITICAL,
                    'high': ReportLevel.ERROR,
                    'medium': ReportLevel.WARNING,
                    'low': ReportLevel.INFO
                }
                return severity_mapping.get(exception.severity, ReportLevel.WARNING)
        
        return ReportLevel.INFO
    
    def _get_traceback(self, exception: Exception) -> Optional[str]:
        """获取异常堆栈信息"""
        try:
            import traceback
            return traceback.format_exc()
        except Exception:
            return None
    
    def _should_report(self, report: ErrorReport) -> bool:
        """判断是否应该报告"""
        for filter_func in self.filters:
            try:
                if not filter_func(report):
                    return False
            except Exception as e:
                self.logger.warning(f"报告过滤器执行失败: {str(e)}")
        
        return True
    
    def _store_report(self, report: ErrorReport):
        """存储报告"""
        with self.lock:
            # 添加到报告列表
            self.reports.append(report)
            
            # 限制报告数量
            if len(self.reports) > self.max_reports:
                self.reports.pop(0)
            
            # 更新统计信息
            self.stats['total_reports'] += 1
            self.stats['reports_by_level'][report.level.value] += 1
            self.stats['reports_by_type'][report.exception_type] = (
                self.stats['reports_by_type'].get(report.exception_type, 0) + 1
            )
            self.stats['last_report_time'] = report.timestamp
    
    def _trigger_callbacks(self, report: ErrorReport):
        """触发报告回调"""
        for callback in self.report_callbacks:
            try:
                callback(report)
            except Exception as e:
                self.logger.error(f"报告回调执行失败: {str(e)}")
    
    def _write_to_file(self, report: ErrorReport):
        """写入报告文件"""
        try:
            report_file_path = Path(self.report_file)
            report_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_file_path, 'a', encoding='utf-8') as f:
                f.write(report.to_json() + '\n')
                
        except Exception as e:
            self.logger.error(f"写入报告文件失败: {str(e)}")
    
    def get_reports(self, level: ReportLevel = None, limit: int = None,
                   start_time: float = None, end_time: float = None) -> List[ErrorReport]:
        """
        获取报告列表
        
        Args:
            level: 报告级别过滤
            limit: 返回数量限制
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            报告列表
        """
        with self.lock:
            reports = self.reports.copy()
        
        # 应用过滤条件
        if level:
            reports = [r for r in reports if r.level == level]
        
        if start_time:
            reports = [r for r in reports if r.timestamp >= start_time]
        
        if end_time:
            reports = [r for r in reports if r.timestamp <= end_time]
        
        # 按时间倒序排列
        reports.sort(key=lambda r: r.timestamp, reverse=True)
        
        # 应用数量限制
        if limit:
            reports = reports[:limit]
        
        return reports
    
    def get_report_by_id(self, report_id: str) -> Optional[ErrorReport]:
        """
        根据ID获取报告
        
        Args:
            report_id: 报告ID
            
        Returns:
            报告对象或None
        """
        with self.lock:
            for report in self.reports:
                if report.id == report_id:
                    return report
        
        return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self.lock:
            stats = self.stats.copy()
            stats['current_reports'] = len(self.reports)
            stats['max_reports'] = self.max_reports
        
        return stats
    
    def export_reports(self, file_path: str, format: str = 'json',
                      level: ReportLevel = None, limit: int = None):
        """
        导出报告
        
        Args:
            file_path: 导出文件路径
            format: 导出格式 (json, csv)
            level: 报告级别过滤
            limit: 导出数量限制
        """
        reports = self.get_reports(level=level, limit=limit)
        
        try:
            export_path = Path(file_path)
            export_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format.lower() == 'json':
                with open(export_path, 'w', encoding='utf-8') as f:
                    json.dump([report.to_dict() for report in reports], f, 
                             ensure_ascii=False, indent=2)
            
            elif format.lower() == 'csv':
                import csv
                
                with open(export_path, 'w', newline='', encoding='utf-8') as f:
                    if reports:
                        writer = csv.DictWriter(f, fieldnames=reports[0].to_dict().keys())
                        writer.writeheader()
                        for report in reports:
                            writer.writerow(report.to_dict())
            
            self.logger.info(f"报告导出完成: {file_path}")
            
        except Exception as e:
            self.logger.error(f"导出报告失败: {str(e)}")
            raise
    
    def clear_reports(self, before_time: float = None):
        """
        清理报告
        
        Args:
            before_time: 清理此时间之前的报告，None表示清理所有
        """
        with self.lock:
            if before_time is None:
                cleared_count = len(self.reports)
                self.reports.clear()
            else:
                original_count = len(self.reports)
                self.reports = [r for r in self.reports if r.timestamp >= before_time]
                cleared_count = original_count - len(self.reports)
        
        self.logger.info(f"清理了 {cleared_count} 个报告")
    
    def generate_summary(self, hours: int = 24) -> Dict[str, Any]:
        """
        生成报告摘要
        
        Args:
            hours: 统计时间范围（小时）
            
        Returns:
            摘要信息
        """
        start_time = time.time() - (hours * 3600)
        recent_reports = self.get_reports(start_time=start_time)
        
        summary = {
            'time_range': f"最近 {hours} 小时",
            'total_reports': len(recent_reports),
            'reports_by_level': {},
            'reports_by_type': {},
            'top_errors': [],
            'error_trend': []
        }
        
        # 按级别统计
        for level in ReportLevel:
            count = len([r for r in recent_reports if r.level == level])
            summary['reports_by_level'][level.value] = count
        
        # 按类型统计
        type_counts = {}
        for report in recent_reports:
            type_counts[report.exception_type] = type_counts.get(report.exception_type, 0) + 1
        
        summary['reports_by_type'] = type_counts
        
        # 最常见的错误
        summary['top_errors'] = sorted(type_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return summary


# 全局错误报告器实例
_global_error_reporter: Optional[ErrorReporter] = None


def get_global_error_reporter() -> ErrorReporter:
    """获取全局错误报告器实例"""
    global _global_error_reporter
    if _global_error_reporter is None:
        _global_error_reporter = ErrorReporter(report_file="logs/error_reports.jsonl")
    return _global_error_reporter


def report_error(exception: Exception, context: ErrorContext = None, **kwargs) -> str:
    """便捷的错误报告函数"""
    return get_global_error_reporter().report_exception(exception, context, **kwargs)