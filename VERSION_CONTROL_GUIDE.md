# 版本控制和回滚系统使用指南

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
python version_control_system.py create v1.1.0 \
    --description "重构WebPageParser类" \
    --scope "src/core/parser.py" "src/core/extractor.py" \
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
