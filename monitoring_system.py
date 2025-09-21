#!/usr/bin/env python3
"""
监控告警系统
用于监控核心指标并在异常时触发回滚预案
"""

import time
import json
import logging
import threading
import psutil
import requests
from typing import Dict, List, Callable, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import smtplib
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart


@dataclass
class MetricThreshold:
    """指标阈值配置"""
    name: str
    warning_threshold: float
    critical_threshold: float
    unit: str
    check_interval: int  # 检查间隔（秒）
    consecutive_failures: int  # 连续失败次数触发告警


@dataclass
class AlertRule:
    """告警规则"""
    rule_id: str
    metric_name: str
    condition: str  # >, <, ==, !=
    threshold: float
    severity: str  # info, warning, critical
    action: str  # log, email, rollback
    enabled: bool


@dataclass
class MonitoringEvent:
    """监控事件"""
    event_id: str
    timestamp: str
    metric_name: str
    current_value: float
    threshold_value: float
    severity: str
    message: str
    action_taken: str


class SystemMonitor:
    """系统监控器"""
    
    def __init__(self, config_file: str = "monitoring_config.json"):
        self.config_file = Path(config_file)
        self.events_log = Path("monitoring_events.json")
        self.is_running = False
        self.monitor_threads = []
        
        # 配置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('monitoring.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 初始化配置
        self._init_config()
        self.load_config()
        
        # 指标历史数据
        self.metrics_history: Dict[str, List] = {}
        
        # 告警状态跟踪
        self.alert_states: Dict[str, Dict] = {}
    
    def _init_config(self):
        """初始化监控配置"""
        if not self.config_file.exists():
            default_config = {
                "metrics": [
                    {
                        "name": "cpu_usage",
                        "warning_threshold": 70.0,
                        "critical_threshold": 90.0,
                        "unit": "%",
                        "check_interval": 30,
                        "consecutive_failures": 3
                    },
                    {
                        "name": "memory_usage",
                        "warning_threshold": 80.0,
                        "critical_threshold": 95.0,
                        "unit": "%",
                        "check_interval": 30,
                        "consecutive_failures": 3
                    },
                    {
                        "name": "disk_usage",
                        "warning_threshold": 85.0,
                        "critical_threshold": 95.0,
                        "unit": "%",
                        "check_interval": 60,
                        "consecutive_failures": 2
                    },
                    {
                        "name": "response_time",
                        "warning_threshold": 1000.0,
                        "critical_threshold": 3000.0,
                        "unit": "ms",
                        "check_interval": 60,
                        "consecutive_failures": 3
                    },
                    {
                        "name": "error_rate",
                        "warning_threshold": 5.0,
                        "critical_threshold": 10.0,
                        "unit": "%",
                        "check_interval": 60,
                        "consecutive_failures": 2
                    }
                ],
                "alert_rules": [
                    {
                        "rule_id": "cpu_critical",
                        "metric_name": "cpu_usage",
                        "condition": ">",
                        "threshold": 90.0,
                        "severity": "critical",
                        "action": "rollback",
                        "enabled": True
                    },
                    {
                        "rule_id": "memory_critical",
                        "metric_name": "memory_usage",
                        "condition": ">",
                        "threshold": 95.0,
                        "severity": "critical",
                        "action": "rollback",
                        "enabled": True
                    },
                    {
                        "rule_id": "error_rate_high",
                        "metric_name": "error_rate",
                        "condition": ">",
                        "threshold": 10.0,
                        "severity": "critical",
                        "action": "rollback",
                        "enabled": True
                    }
                ],
                "notification": {
                    "email": {
                        "enabled": False,
                        "smtp_server": "smtp.gmail.com",
                        "smtp_port": 587,
                        "username": "",
                        "password": "",
                        "recipients": []
                    },
                    "webhook": {
                        "enabled": False,
                        "url": "",
                        "headers": {}
                    }
                },
                "rollback": {
                    "enabled": True,
                    "auto_rollback_threshold": "critical",
                    "rollback_delay_seconds": 300,  # 5分钟延迟
                    "max_rollbacks_per_hour": 3
                }
            }
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    def load_config(self):
        """加载监控配置"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            self.metrics = [MetricThreshold(**m) for m in config["metrics"]]
            self.alert_rules = [AlertRule(**r) for r in config["alert_rules"]]
            self.notification_config = config["notification"]
            self.rollback_config = config["rollback"]
            
            self.logger.info("监控配置加载成功")
            
        except Exception as e:
            self.logger.error(f"加载监控配置失败: {str(e)}")
            raise
    
    def start_monitoring(self):
        """启动监控"""
        if self.is_running:
            self.logger.warning("监控已在运行中")
            return
        
        self.is_running = True
        self.logger.info("启动系统监控")
        
        # 为每个指标启动监控线程
        for metric in self.metrics:
            thread = threading.Thread(
                target=self._monitor_metric,
                args=(metric,),
                daemon=True
            )
            thread.start()
            self.monitor_threads.append(thread)
        
        # 启动告警处理线程
        alert_thread = threading.Thread(
            target=self._process_alerts,
            daemon=True
        )
        alert_thread.start()
        self.monitor_threads.append(alert_thread)
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        self.logger.info("停止系统监控")
        
        # 等待所有线程结束
        for thread in self.monitor_threads:
            thread.join(timeout=5)
        
        self.monitor_threads.clear()
    
    def _monitor_metric(self, metric: MetricThreshold):
        """监控单个指标"""
        consecutive_failures = 0
        
        while self.is_running:
            try:
                # 获取指标值
                current_value = self._get_metric_value(metric.name)
                
                # 记录历史数据
                self._record_metric_history(metric.name, current_value)
                
                # 检查阈值
                if current_value >= metric.critical_threshold:
                    consecutive_failures += 1
                    severity = "critical"
                elif current_value >= metric.warning_threshold:
                    consecutive_failures += 1
                    severity = "warning"
                else:
                    consecutive_failures = 0
                    severity = "normal"
                
                # 触发告警
                if consecutive_failures >= metric.consecutive_failures and severity != "normal":
                    self._trigger_alert(metric.name, current_value, severity)
                
                # 重置连续失败计数
                if severity == "normal":
                    self._clear_alert_state(metric.name)
                
                time.sleep(metric.check_interval)
                
            except Exception as e:
                self.logger.error(f"监控指标 {metric.name} 时出错: {str(e)}")
                time.sleep(metric.check_interval)
    
    def _get_metric_value(self, metric_name: str) -> float:
        """获取指标值"""
        try:
            if metric_name == "cpu_usage":
                return psutil.cpu_percent(interval=1)
            
            elif metric_name == "memory_usage":
                memory = psutil.virtual_memory()
                return memory.percent
            
            elif metric_name == "disk_usage":
                disk = psutil.disk_usage('/')
                return (disk.used / disk.total) * 100
            
            elif metric_name == "response_time":
                # 模拟响应时间检查
                start_time = time.time()
                try:
                    # 这里可以替换为实际的健康检查端点
                    response = requests.get("http://localhost:8000/health", timeout=5)
                    response_time = (time.time() - start_time) * 1000
                    return response_time
                except:
                    return 5000.0  # 超时返回高响应时间
            
            elif metric_name == "error_rate":
                # 模拟错误率计算
                # 实际实现中应该从日志或监控系统获取
                return self._calculate_error_rate()
            
            else:
                self.logger.warning(f"未知的指标类型: {metric_name}")
                return 0.0
                
        except Exception as e:
            self.logger.error(f"获取指标 {metric_name} 失败: {str(e)}")
            return 0.0
    
    def _calculate_error_rate(self) -> float:
        """计算错误率"""
        try:
            # 这里应该实现实际的错误率计算逻辑
            # 例如从日志文件中统计错误数量
            log_file = Path("version_control.log")
            if not log_file.exists():
                return 0.0
            
            # 简单的错误率计算示例
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 只检查最近100行日志
            recent_lines = lines[-100:] if len(lines) > 100 else lines
            error_count = sum(1 for line in recent_lines if "ERROR" in line)
            
            if len(recent_lines) == 0:
                return 0.0
            
            return (error_count / len(recent_lines)) * 100
            
        except Exception as e:
            self.logger.error(f"计算错误率失败: {str(e)}")
            return 0.0
    
    def _record_metric_history(self, metric_name: str, value: float):
        """记录指标历史数据"""
        if metric_name not in self.metrics_history:
            self.metrics_history[metric_name] = []
        
        timestamp = datetime.now().isoformat()
        self.metrics_history[metric_name].append({
            "timestamp": timestamp,
            "value": value
        })
        
        # 只保留最近1000个数据点
        if len(self.metrics_history[metric_name]) > 1000:
            self.metrics_history[metric_name] = self.metrics_history[metric_name][-1000:]
    
    def _trigger_alert(self, metric_name: str, current_value: float, severity: str):
        """触发告警"""
        # 检查是否已经在告警状态
        if metric_name in self.alert_states:
            last_alert = self.alert_states[metric_name]
            # 避免重复告警（5分钟内不重复）
            if datetime.now() - datetime.fromisoformat(last_alert["timestamp"]) < timedelta(minutes=5):
                return
        
        # 创建告警事件
        event = MonitoringEvent(
            event_id=f"{metric_name}_{int(time.time())}",
            timestamp=datetime.now().isoformat(),
            metric_name=metric_name,
            current_value=current_value,
            threshold_value=self._get_threshold_for_severity(metric_name, severity),
            severity=severity,
            message=f"指标 {metric_name} 异常: 当前值 {current_value}",
            action_taken=""
        )
        
        # 记录告警状态
        self.alert_states[metric_name] = {
            "timestamp": event.timestamp,
            "severity": severity,
            "value": current_value
        }
        
        # 处理告警
        self._handle_alert(event)
        
        # 保存事件
        self._save_event(event)
    
    def _handle_alert(self, event: MonitoringEvent):
        """处理告警"""
        self.logger.warning(f"告警触发: {event.message}")
        
        # 查找匹配的告警规则
        for rule in self.alert_rules:
            if (rule.metric_name == event.metric_name and 
                rule.enabled and 
                self._evaluate_condition(event.current_value, rule.condition, rule.threshold)):
                
                self.logger.info(f"执行告警规则: {rule.rule_id}")
                
                if rule.action == "email":
                    self._send_email_notification(event)
                elif rule.action == "webhook":
                    self._send_webhook_notification(event)
                elif rule.action == "rollback":
                    self._trigger_auto_rollback(event)
                
                event.action_taken = rule.action
                break
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """评估条件"""
        if condition == ">":
            return value > threshold
        elif condition == "<":
            return value < threshold
        elif condition == "==":
            return abs(value - threshold) < 0.001
        elif condition == "!=":
            return abs(value - threshold) >= 0.001
        else:
            return False
    
    def _trigger_auto_rollback(self, event: MonitoringEvent):
        """触发自动回滚"""
        if not self.rollback_config["enabled"]:
            self.logger.info("自动回滚已禁用")
            return
        
        if event.severity != self.rollback_config["auto_rollback_threshold"]:
            self.logger.info(f"告警级别 {event.severity} 不满足自动回滚条件")
            return
        
        # 检查回滚频率限制
        if not self._check_rollback_rate_limit():
            self.logger.warning("回滚频率超限，跳过自动回滚")
            return
        
        self.logger.critical(f"触发自动回滚: {event.message}")
        
        # 延迟执行回滚
        delay = self.rollback_config["rollback_delay_seconds"]
        self.logger.info(f"将在 {delay} 秒后执行回滚")
        
        def delayed_rollback():
            time.sleep(delay)
            try:
                from version_control_system import VersionControlSystem
                vcs = VersionControlSystem()
                stable_versions = vcs.get_stable_versions(limit=1)
                
                if stable_versions:
                    target_version = stable_versions[0].tag
                    reason = f"自动回滚 - 指标异常: {event.message}"
                    success = vcs.rollback_to_version(target_version, reason)
                    
                    if success:
                        self.logger.info(f"自动回滚成功: {target_version}")
                        self._record_rollback_event(target_version, reason, True)
                    else:
                        self.logger.error("自动回滚失败")
                        self._record_rollback_event(target_version, reason, False)
                else:
                    self.logger.error("没有可用的稳定版本进行回滚")
                    
            except Exception as e:
                self.logger.error(f"自动回滚过程出错: {str(e)}")
        
        # 在后台线程中执行回滚
        rollback_thread = threading.Thread(target=delayed_rollback, daemon=True)
        rollback_thread.start()
    
    def _check_rollback_rate_limit(self) -> bool:
        """检查回滚频率限制"""
        max_rollbacks = self.rollback_config["max_rollbacks_per_hour"]
        
        # 统计最近一小时的回滚次数
        one_hour_ago = datetime.now() - timedelta(hours=1)
        
        try:
            if not self.events_log.exists():
                return True
            
            with open(self.events_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            recent_rollbacks = 0
            for event_data in data.get("events", []):
                event_time = datetime.fromisoformat(event_data["timestamp"])
                if (event_time > one_hour_ago and 
                    event_data.get("action_taken") == "rollback"):
                    recent_rollbacks += 1
            
            return recent_rollbacks < max_rollbacks
            
        except Exception as e:
            self.logger.error(f"检查回滚频率限制失败: {str(e)}")
            return True
    
    def _send_email_notification(self, event: MonitoringEvent):
        """发送邮件通知"""
        if not self.notification_config["email"]["enabled"]:
            return
        
        try:
            config = self.notification_config["email"]
            
            msg = MimeMultipart()
            msg['From'] = config["username"]
            msg['To'] = ", ".join(config["recipients"])
            msg['Subject'] = f"系统监控告警 - {event.severity.upper()}"
            
            body = f"""
系统监控告警通知

告警时间: {event.timestamp}
指标名称: {event.metric_name}
当前值: {event.current_value}
阈值: {event.threshold_value}
严重程度: {event.severity}
详细信息: {event.message}

请及时处理相关问题。
"""
            
            msg.attach(MimeText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
            server.starttls()
            server.login(config["username"], config["password"])
            server.send_message(msg)
            server.quit()
            
            self.logger.info("邮件通知发送成功")
            
        except Exception as e:
            self.logger.error(f"发送邮件通知失败: {str(e)}")
    
    def _send_webhook_notification(self, event: MonitoringEvent):
        """发送Webhook通知"""
        if not self.notification_config["webhook"]["enabled"]:
            return
        
        try:
            config = self.notification_config["webhook"]
            
            payload = {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "metric_name": event.metric_name,
                "current_value": event.current_value,
                "threshold_value": event.threshold_value,
                "severity": event.severity,
                "message": event.message
            }
            
            response = requests.post(
                config["url"],
                json=payload,
                headers=config.get("headers", {}),
                timeout=10
            )
            
            if response.status_code == 200:
                self.logger.info("Webhook通知发送成功")
            else:
                self.logger.error(f"Webhook通知发送失败: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"发送Webhook通知失败: {str(e)}")
    
    def _get_threshold_for_severity(self, metric_name: str, severity: str) -> float:
        """获取指定严重程度的阈值"""
        for metric in self.metrics:
            if metric.name == metric_name:
                if severity == "critical":
                    return metric.critical_threshold
                elif severity == "warning":
                    return metric.warning_threshold
        return 0.0
    
    def _clear_alert_state(self, metric_name: str):
        """清除告警状态"""
        if metric_name in self.alert_states:
            del self.alert_states[metric_name]
    
    def _save_event(self, event: MonitoringEvent):
        """保存监控事件"""
        try:
            if not self.events_log.exists():
                data = {"events": []}
            else:
                with open(self.events_log, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            
            data["events"].append(asdict(event))
            
            # 只保留最近1000个事件
            if len(data["events"]) > 1000:
                data["events"] = data["events"][-1000:]
            
            with open(self.events_log, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"保存监控事件失败: {str(e)}")
    
    def _record_rollback_event(self, version: str, reason: str, success: bool):
        """记录回滚事件"""
        event = MonitoringEvent(
            event_id=f"rollback_{int(time.time())}",
            timestamp=datetime.now().isoformat(),
            metric_name="system",
            current_value=0.0,
            threshold_value=0.0,
            severity="critical",
            message=f"自动回滚到版本 {version}: {reason}",
            action_taken="rollback"
        )
        
        self._save_event(event)
    
    def _process_alerts(self):
        """处理告警队列"""
        while self.is_running:
            try:
                # 这里可以实现更复杂的告警处理逻辑
                # 例如告警聚合、去重等
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"处理告警时出错: {str(e)}")
                time.sleep(10)
    
    def get_current_metrics(self) -> Dict[str, float]:
        """获取当前所有指标值"""
        metrics = {}
        for metric in self.metrics:
            metrics[metric.name] = self._get_metric_value(metric.name)
        return metrics
    
    def get_metric_history(self, metric_name: str, hours: int = 24) -> List[Dict]:
        """获取指标历史数据"""
        if metric_name not in self.metrics_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        history = self.metrics_history[metric_name]
        
        return [
            point for point in history
            if datetime.fromisoformat(point["timestamp"]) > cutoff_time
        ]
    
    def get_recent_events(self, hours: int = 24) -> List[MonitoringEvent]:
        """获取最近的监控事件"""
        try:
            if not self.events_log.exists():
                return []
            
            with open(self.events_log, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_events = []
            
            for event_data in data.get("events", []):
                event_time = datetime.fromisoformat(event_data["timestamp"])
                if event_time > cutoff_time:
                    recent_events.append(MonitoringEvent(**event_data))
            
            return sorted(recent_events, key=lambda x: x.timestamp, reverse=True)
            
        except Exception as e:
            self.logger.error(f"获取最近事件失败: {str(e)}")
            return []


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="监控告警系统")
    parser.add_argument('--config', default='monitoring_config.json', help='配置文件路径')
    parser.add_argument('--daemon', action='store_true', help='后台运行')
    
    args = parser.parse_args()
    
    monitor = SystemMonitor(args.config)
    
    try:
        monitor.start_monitoring()
        
        if args.daemon:
            # 后台运行模式
            while True:
                time.sleep(60)
        else:
            # 交互模式
            print("监控系统已启动，按 Ctrl+C 停止")
            while True:
                time.sleep(1)
                
    except KeyboardInterrupt:
        print("\n正在停止监控系统...")
        monitor.stop_monitoring()
        print("监控系统已停止")


if __name__ == "__main__":
    main()