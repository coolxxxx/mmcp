
# 服务器友好下载配置使用说明

## 配置特点
- **保守的并发**: 6个线程，避免服务器过载
- **温和的速率**: 3-8 req/s，减少触发反爬机制
- **充足的超时**: 45秒超时，给服务器足够响应时间
- **增强的重试**: 4次重试，提高成功率
- **智能延迟**: 请求间隔0.5秒，避免过于频繁

## 502错误应对策略
1. **检测机制**: 自动检测连续502错误
2. **保护模式**: 连续3次502错误后自动降速
3. **冷却恢复**: 30秒冷却后尝试恢复
4. **逐步恢复**: 分5步逐步恢复正常速度

## 使用方法
```python
from src.core.final_integration import create_optimized_downloader

# 创建优化的下载管理器
downloader = create_optimized_downloader(file_manager)

# 下载图片
success = downloader.download_image(image_info)

# 获取服务器状态
status = downloader.get_server_status()
print(f"服务器健康状态: {status['is_healthy']}")
```

## 监控建议
- 关注502错误频率
- 监控服务器响应时间
- 观察成功率变化
- 根据服务器状况调整参数
