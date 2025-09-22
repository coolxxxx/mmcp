"""
最终集成方案
应用服务器友好配置，避免502错误
"""

import os
import sys
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.server_friendly_config import get_server_friendly_config
from src.core.adaptive_downloader import AdaptiveDownloadManager


def apply_server_friendly_optimization():
    """应用服务器友好的优化配置"""
    print("=" * 60)
    print("应用服务器友好优化配置")
    print("=" * 60)
    
    # 加载服务器友好配置
    config = get_server_friendly_config()
    
    print("当前配置特点:")
    print(f"✓ 线程数: {config.max_threads} (保守，避免服务器过载)")
    print(f"✓ 请求速率: {config.base_rate}-{config.max_rate} req/s (温和)")
    print(f"✓ 超时时间: {config.timeout}s (充足响应时间)")
    print(f"✓ 重试次数: {config.retry_times} (增强容错)")
    print(f"✓ 服务器错误延迟: {config.server_error_delay}s")
    print(f"✓ 请求间隔: {config.request_interval}s (避免过于频繁)")
    print(f"✓ 分片下载: {'启用' if config.enable_chunked_download else '禁用'} (减少复杂性)")
    print(f"✓ 指数退避: {'启用' if config.exponential_backoff else '禁用'}")
    
    print("\n针对502错误的特殊优化:")
    print(f"✓ 502错误专用重试次数: {config.server_error_retry_times}")
    print(f"✓ 502错误后冷却时间: {config.server_error_cooldown}s")
    print(f"✓ 连续502错误保护机制: 自动降速")
    print(f"✓ 服务器恢复检测: 智能恢复")
    
    return config


def create_optimized_downloader(file_manager=None):
    """创建优化的下载管理器"""
    config = get_server_friendly_config()
    
    # 创建自适应下载管理器
    downloader = AdaptiveDownloadManager(
        config=config.to_dict(),
        file_manager=file_manager
    )
    
    return downloader


def update_existing_system():
    """更新现有系统配置"""
    try:
        # 更新默认配置文件
        config = get_server_friendly_config()
        
        # 保存为默认优化配置
        default_config_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'config', 'download_optimization.json'
        )
        config.save_to_file(default_config_path)
        
        print(f"\n✓ 已更新默认配置文件: {default_config_path}")
        
        # 创建使用说明
        usage_guide = """
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
"""
        
        usage_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'docs', 'server_friendly_usage.md'
        )
        os.makedirs(os.path.dirname(usage_path), exist_ok=True)
        
        with open(usage_path, 'w', encoding='utf-8') as f:
            f.write(usage_guide)
        
        print(f"✓ 已创建使用说明: {usage_path}")
        
        return True
        
    except Exception as e:
        print(f"✗ 更新系统配置失败: {e}")
        return False


def main():
    """主函数"""
    print("开始应用服务器友好优化...")
    
    # 应用配置
    config = apply_server_friendly_optimization()
    
    # 更新系统
    if update_existing_system():
        print("\n" + "=" * 60)
        print("服务器友好优化应用完成！")
        print("=" * 60)
        
        print("\n主要改进:")
        print("1. 大幅降低并发压力 - 从15线程降至6线程")
        print("2. 温和的请求速率 - 从20req/s降至3-8req/s")
        print("3. 增加服务器响应时间 - 超时从20s增至45s")
        print("4. 智能502错误处理 - 自动检测和恢复机制")
        print("5. 保护模式机制 - 连续错误时自动降速")
        print("6. 指数退避重试 - 避免对服务器造成额外压力")
        
        print("\n这些优化将显著减少502错误的发生，")
        print("同时保持合理的下载效率和用户体验。")
        
        print("\n建议:")
        print("- 在服务器繁忙时段使用此配置")
        print("- 监控502错误频率，必要时进一步调整")
        print("- 如果服务器状况改善，可适当提高参数")
        
    else:
        print("✗ 优化应用失败")


if __name__ == "__main__":
    main()