"""
异步执行器
提供异步任务执行和协程管理
"""

import asyncio
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Awaitable, Union
from dataclasses import dataclass
from enum import Enum
import logging
from concurrent.futures import Future


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class AsyncTask:
    """异步任务"""
    coro: Awaitable[Any]
    priority: TaskPriority = TaskPriority.NORMAL
    timeout: Optional[float] = None
    callback: Optional[Callable[[Any], None]] = None
    error_callback: Optional[Callable[[Exception], None]] = None
    created_time: float = 0.0
    
    def __post_init__(self):
        if self.created_time == 0.0:
            self.created_time = time.time()
    
    def __lt__(self, other):
        # 优先级高的任务排在前面，同优先级按创建时间排序
        return (self.priority.value, -self.created_time) > (other.priority.value, -other.created_time)


class AsyncExecutor:
    """异步执行器"""
    
    def __init__(self, max_concurrent: int = 10, loop: Optional[asyncio.AbstractEventLoop] = None):
        """
        初始化异步执行器
        
        Args:
            max_concurrent: 最大并发数
            loop: 事件循环
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_concurrent = max_concurrent
        self.loop = loop
        
        # 任务管理
        self.pending_tasks: List[AsyncTask] = []
        self.running_tasks: Dict[asyncio.Task, AsyncTask] = {}
        self.completed_tasks: List[AsyncTask] = []
        self.failed_tasks: List[AsyncTask] = []
        
        # 信号量控制并发
        self.semaphore: Optional[asyncio.Semaphore] = None
        
        # 统计信息
        self.stats = {
            'total_submitted': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0,
            'avg_execution_time': 0.0,
            'total_execution_time': 0.0
        }
        
        # 线程安全锁
        self.lock = threading.Lock()
        
        self.logger.info(f"异步执行器初始化完成，最大并发数: {max_concurrent}")
    
    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        """确保有可用的事件循环"""
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)
        
        if self.semaphore is None:
            self.semaphore = asyncio.Semaphore(self.max_concurrent)
        
        return self.loop
    
    async def submit_async(self, coro: Awaitable[Any], priority: TaskPriority = TaskPriority.NORMAL,
                          timeout: Optional[float] = None, 
                          callback: Optional[Callable[[Any], None]] = None,
                          error_callback: Optional[Callable[[Exception], None]] = None) -> asyncio.Task:
        """
        提交异步任务
        
        Args:
            coro: 协程对象
            priority: 任务优先级
            timeout: 超时时间
            callback: 成功回调
            error_callback: 错误回调
            
        Returns:
            asyncio.Task对象
        """
        self._ensure_loop()

        task_obj = AsyncTask(
            coro=coro,
            priority=priority,
            timeout=timeout,
            callback=callback,
            error_callback=error_callback
        )
        
        with self.lock:
            self.stats['total_submitted'] += 1
        
        # 创建任务
        task = asyncio.create_task(self._execute_task(task_obj))
        
        with self.lock:
            self.running_tasks[task] = task_obj
        
        return task
    
    async def _execute_task(self, task_obj: AsyncTask) -> Any:
        """
        执行单个任务
        
        Args:
            task_obj: 任务对象
            
        Returns:
            任务结果
        """
        start_time = time.time()
        
        async with self.semaphore:
            try:
                # 执行任务
                if task_obj.timeout:
                    result = await asyncio.wait_for(task_obj.coro, timeout=task_obj.timeout)
                else:
                    result = await task_obj.coro
                
                # 执行成功回调
                if task_obj.callback:
                    try:
                        if asyncio.iscoroutinefunction(task_obj.callback):
                            await task_obj.callback(result)
                        else:
                            task_obj.callback(result)
                    except Exception as e:
                        self.logger.warning(f"任务回调执行失败: {str(e)}")
                
                # 更新统计
                execution_time = time.time() - start_time
                with self.lock:
                    self.stats['total_completed'] += 1
                    self.stats['total_execution_time'] += execution_time
                    if self.stats['total_completed'] > 0:
                        self.stats['avg_execution_time'] = (
                            self.stats['total_execution_time'] / self.stats['total_completed']
                        )
                    self.completed_tasks.append(task_obj)
                
                return result
                
            except asyncio.TimeoutError:
                self.logger.warning("任务执行超时")
                with self.lock:
                    self.stats['total_cancelled'] += 1
                    self.failed_tasks.append(task_obj)
                raise
                
            except Exception as e:
                # 执行错误回调
                if task_obj.error_callback:
                    try:
                        if asyncio.iscoroutinefunction(task_obj.error_callback):
                            await task_obj.error_callback(e)
                        else:
                            task_obj.error_callback(e)
                    except Exception as callback_error:
                        self.logger.warning(f"错误回调执行失败: {str(callback_error)}")
                
                # 更新统计
                with self.lock:
                    self.stats['total_failed'] += 1
                    self.failed_tasks.append(task_obj)
                
                self.logger.error(f"任务执行失败: {str(e)}")
                raise
            
            finally:
                # 清理任务
                current_task = asyncio.current_task()
                if current_task and current_task in self.running_tasks:
                    with self.lock:
                        del self.running_tasks[current_task]
    
    def submit_sync(self, coro: Awaitable[Any], priority: TaskPriority = TaskPriority.NORMAL,
                   timeout: Optional[float] = None) -> Future:
        """
        同步方式提交异步任务
        
        Args:
            coro: 协程对象
            priority: 任务优先级
            timeout: 超时时间
            
        Returns:
            Future对象
        """
        loop = self._ensure_loop()
        
        # 如果当前在事件循环中，直接创建任务
        try:
            current_loop = asyncio.get_running_loop()
            if current_loop == loop:
                task = asyncio.create_task(self.submit_async(coro, priority, timeout))
                return asyncio.wrap_future(asyncio.ensure_future(task))
        except RuntimeError:
            pass
        
        # 在新线程中运行事件循环
        def run_in_thread():
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(self.submit_async(coro, priority, timeout))
        
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(run_in_thread)
    
    async def submit_batch(self, coros: List[Awaitable[Any]], 
                          priority: TaskPriority = TaskPriority.NORMAL,
                          timeout: Optional[float] = None,
                          return_when: str = 'ALL_COMPLETED') -> List[Any]:
        """
        批量提交异步任务
        
        Args:
            coros: 协程列表
            priority: 任务优先级
            timeout: 超时时间
            return_when: 返回条件
            
        Returns:
            结果列表
        """
        tasks = []
        for coro in coros:
            task = await self.submit_async(coro, priority, timeout)
            tasks.append(task)
        
        # 等待任务完成
        if return_when == 'FIRST_COMPLETED':
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
            # 取消未完成的任务
            for task in pending:
                task.cancel()
        else:
            done, pending = await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED, timeout=timeout)
        
        # 收集结果
        results = []
        for task in done:
            try:
                result = await task
                results.append(result)
            except Exception as e:
                results.append(e)
        
        return results
    
    async def map_async(self, func: Callable, items: List[Any], 
                       priority: TaskPriority = TaskPriority.NORMAL,
                       timeout: Optional[float] = None) -> List[Any]:
        """
        异步映射函数
        
        Args:
            func: 要应用的函数
            items: 数据列表
            priority: 任务优先级
            timeout: 超时时间
            
        Returns:
            结果列表
        """
        # 创建协程列表
        if asyncio.iscoroutinefunction(func):
            coros = [func(item) for item in items]
        else:
            # 将同步函数包装为协程
            async def async_wrapper(item):
                return func(item)
            coros = [async_wrapper(item) for item in items]
        
        return await self.submit_batch(coros, priority, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        with self.lock:
            stats = self.stats.copy()
            stats.update({
                'pending_tasks': len(self.pending_tasks),
                'running_tasks': len(self.running_tasks),
                'completed_tasks': len(self.completed_tasks),
                'failed_tasks': len(self.failed_tasks)
            })
        
        return stats
    
    def clear_completed(self):
        """清理已完成的任务"""
        with self.lock:
            self.completed_tasks.clear()
            self.failed_tasks.clear()
    
    async def shutdown(self, wait: bool = True):
        """
        关闭执行器
        
        Args:
            wait: 是否等待任务完成
        """
        if wait:
            # 等待所有运行中的任务完成
            if self.running_tasks:
                await asyncio.gather(*self.running_tasks.keys(), return_exceptions=True)
        else:
            # 取消所有运行中的任务
            for task in self.running_tasks.keys():
                task.cancel()
        
        self.logger.info("异步执行器已关闭")


# 全局异步执行器实例
_global_async_executor: Optional[AsyncExecutor] = None


def get_global_async_executor() -> AsyncExecutor:
    """获取全局异步执行器实例"""
    global _global_async_executor
    if _global_async_executor is None:
        _global_async_executor = AsyncExecutor()
    return _global_async_executor


async def shutdown_global_async_executor():
    """关闭全局异步执行器"""
    global _global_async_executor
    if _global_async_executor:
        await _global_async_executor.shutdown()
        _global_async_executor = None
