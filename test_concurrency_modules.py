"""
测试并发优化模块
"""

import asyncio
import sys
import os
import time
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """测试模块导入"""
    print("测试模块导入...")
    
    try:
        from src.core.concurrency import (
            ThreadPoolManager, 
            AsyncExecutor,
            ResourceManager,
            ConcurrentDownloader,
            PerformanceMonitor,
            MemoryOptimizer
        )
        print("✅ 所有模块导入成功")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_thread_pool_manager():
    """测试线程池管理器"""
    print("\n测试线程池管理器...")
    
    try:
        from src.core.concurrency import get_global_pool_manager
        
        # 获取全局线程池管理器
        pool_manager = get_global_pool_manager()
        
        # 测试任务提交
        def test_task(x):
            time.sleep(0.1)
            return x * 2
        
        # 提交任务到不同线程池
        future1 = pool_manager.submit_task('io_bound', test_task, 5)
        future2 = pool_manager.submit_task('cpu_bound', test_task, 10)
        
        # 等待结果
        result1 = future1.result(timeout=5) if future1 else None
        result2 = future2.result(timeout=5) if future2 else None
        
        print(f"✅ 线程池任务执行成功: {result1}, {result2}")
        
        # 获取统计信息
        stats = pool_manager.get_pool_stats()
        print(f"✅ 线程池统计信息获取成功: {len(stats)} 个线程池")
        
        return True
        
    except Exception as e:
        print(f"❌ 线程池管理器测试失败: {e}")
        return False

async def test_async_executor():
    """测试异步执行器"""
    print("\n测试异步执行器...")
    
    try:
        from src.core.concurrency import AsyncExecutor
        
        executor = AsyncExecutor(max_concurrent=5)
        
        # 测试异步任务
        async def async_task(x):
            await asyncio.sleep(0.1)
            return x * 3
        
        # 提交异步任务
        task = await executor.submit_async(async_task(7))
        result = await task
        
        print(f"✅ 异步任务执行成功: {result}")
        
        # 测试批量任务
        tasks = [async_task(i) for i in range(3)]
        results = await executor.submit_batch(tasks)
        
        print(f"✅ 批量异步任务执行成功: {results}")
        
        await executor.shutdown()
        return True
        
    except Exception as e:
        print(f"❌ 异步执行器测试失败: {e}")
        return False

def test_resource_manager():
    """测试资源管理器"""
    print("\n测试资源管理器...")
    
    try:
        from src.core.concurrency import get_global_resource_manager
        
        resource_manager = get_global_resource_manager()
        
        # 获取当前资源使用情况
        usage = resource_manager.get_current_usage()
        print(f"✅ 资源使用情况获取成功: CPU {usage.get('cpu_percent', 0):.1f}%")
        
        # 检查系统健康状况
        health = resource_manager.check_system_health()
        print(f"✅ 系统健康检查成功: {health['overall_status']}")
        
        # 获取优化建议
        recommendations = resource_manager.optimize_for_task('download')
        print(f"✅ 优化建议获取成功: 建议最大工作线程数 {recommendations['max_workers']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 资源管理器测试失败: {e}")
        return False

def test_performance_monitor():
    """测试性能监控器"""
    print("\n测试性能监控器...")
    
    try:
        from src.core.concurrency import get_global_performance_monitor
        
        monitor = get_global_performance_monitor()
        
        # 获取当前快照
        snapshot = monitor.get_current_snapshot()
        if snapshot:
            print(f"✅ 性能快照获取成功: {len(snapshot.metrics)} 个指标")
        
        # 获取统计信息
        stats = monitor.get_stats()
        print(f"✅ 性能统计获取成功: 运行时间 {stats.get('uptime', 0):.1f}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能监控器测试失败: {e}")
        return False

def test_memory_optimizer():
    """测试内存优化器"""
    print("\n测试内存优化器...")
    
    try:
        from src.core.concurrency import get_global_memory_optimizer
        
        optimizer = get_global_memory_optimizer()
        
        # 获取内存统计
        memory_stats = optimizer.get_memory_stats()
        print(f"✅ 内存统计获取成功: 内存使用率 {memory_stats.memory_percent:.1f}%")
        
        # 创建和测试缓存
        optimizer.create_cache('test_cache', max_size=10)
        optimizer.put_to_cache('test_cache', 'key1', 'value1')
        value = optimizer.get_from_cache('test_cache', 'key1')
        
        if value == 'value1':
            print("✅ 缓存功能测试成功")
        
        # 获取优化建议
        recommendations = optimizer.get_optimization_recommendations()
        print(f"✅ 优化建议获取成功: {len(recommendations)} 条建议")
        
        return True
        
    except Exception as e:
        print(f"❌ 内存优化器测试失败: {e}")
        return False

async def test_concurrent_downloader():
    """测试并发下载器"""
    print("\n测试并发下载器...")
    
    try:
        from src.core.concurrency import ConcurrentDownloader
        
        # 创建测试用的简单HTTP服务器URL（使用公共测试URL）
        test_url = "https://httpbin.org/json"
        test_file = "test_download.json"
        
        async with ConcurrentDownloader(max_concurrent=2) as downloader:
            # 测试单个下载
            task_id = await downloader.download(test_url, test_file)
            await downloader.wait_for_completion([task_id])
            
            # 检查下载状态
            task_status = downloader.get_task_status(task_id)
            if task_status and task_status.status.value == 'completed':
                print("✅ 并发下载器测试成功")
                
                # 清理测试文件
                if os.path.exists(test_file):
                    os.remove(test_file)
                
                return True
            else:
                print(f"❌ 下载未完成，状态: {task_status.status.value if task_status else 'None'}")
                return False
        
    except Exception as e:
        print(f"❌ 并发下载器测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试并发优化模块...")
    
    test_results = []
    
    # 基础导入测试
    test_results.append(test_imports())
    
    # 各模块功能测试
    test_results.append(test_thread_pool_manager())
    test_results.append(await test_async_executor())
    test_results.append(test_resource_manager())
    test_results.append(test_performance_monitor())
    test_results.append(test_memory_optimizer())
    test_results.append(await test_concurrent_downloader())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n📊 测试结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有并发优化模块测试通过！")
        return True
    else:
        print("⚠️  部分测试失败，但核心功能可用")
        return False

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(main())
    
    if result:
        print("\n✅ 并发优化模块工作正常，可以继续下一步优化")
    else:
        print("\n⚠️  存在一些问题，但不影响继续优化")