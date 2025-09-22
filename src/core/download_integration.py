"""
下载系统集成模块
整合增强版下载管理器和进度窗口
"""

import os
import sys
from typing import Dict, Any, Optional, List
import threading
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.core.enhanced_downloader import EnhancedDownloadManager
from src.core.download_optimization_config import get_optimized_config
from src.models.data_models import DownloadTask, ImageInfo, DownloadStatus, TaskStatus
from src.utils.logger import setup_logger


class DownloadSystemIntegrator:
    """下载系统集成器"""
    
    def __init__(self, file_manager=None):
        """
        初始化下载系统集成器
        
        Args:
            file_manager: 文件管理器实例
        """
        self.logger = setup_logger('download_integrator')
        self.file_manager = file_manager
        
        # 加载优化配置
        self.config = get_optimized_config()
        self.logger.info("下载优化配置已加载")
        
        # 初始化增强版下载管理器
        self.download_manager = EnhancedDownloadManager(
            config=self.config.to_dict(),
            file_manager=file_manager
        )
        
        # 状态跟踪
        self.active_tasks: Dict[str, DownloadTask] = {}
        self.task_managers: Dict[str, EnhancedDownloadManager] = {}
        
        self.logger.info("下载系统集成器初始化完成")
    
    def start_download_task(self, task: DownloadTask) -> bool:
        """
        启动下载任务
        
        Args:
            task: 下载任务
            
        Returns:
            bool: 是否启动成功
        """
        try:
            self.logger.info(f"启动下载任务: {task.name} (ID: {task.id})")
            
            # 记录任务
            self.active_tasks[task.id] = task
            
            # 为每个任务创建独立的下载管理器
            task_config = self.config.to_dict()
            task_manager = EnhancedDownloadManager(
                config=task_config,
                file_manager=self.file_manager
            )
            
            self.task_managers[task.id] = task_manager
            
            # 启动下载管理器
            task_manager.start()
            
            # 收集所有图片
            all_images = []
            for page in task.pages:
                all_images.extend(page.images)
            
            # 更新任务状态
            task.status = TaskStatus.RUNNING
            task.total_images = len(all_images)
            
            # 批量添加下载任务
            task_manager.start_download_batch(all_images)
            
            # 启动任务监控线程
            monitor_thread = threading.Thread(
                target=self._monitor_task,
                args=(task.id,),
                name=f'task_monitor_{task.id}',
                daemon=True
            )
            monitor_thread.start()
            
            self.logger.info(f"下载任务启动成功: {task.name}, 图片数量: {len(all_images)}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动下载任务失败: {e}", exc_info=True)
            return False
    
    def _monitor_task(self, task_id: str):
        """监控任务进度"""
        try:
            task = self.active_tasks.get(task_id)
            task_manager = self.task_managers.get(task_id)
            
            if not task or not task_manager:
                return
            
            self.logger.info(f"开始监控任务: {task.name}")
            
            while task_manager.is_downloading():
                try:
                    # 获取下载统计
                    stats = task_manager.get_download_stats()
                    
                    # 更新任务状态
                    task.downloaded_images = stats.get('downloaded_images', 0)
                    task.failed_images = stats.get('failed_images', 0)
                    task.downloaded_size = stats.get('downloaded_size', 0)
                    
                    # 计算进度
                    if task.total_images > 0:
                        progress_value = (task.downloaded_images / task.total_images) * 100
                        # 使用 setattr 设置进度，避免属性类型冲突
                        setattr(task, '_progress', progress_value)
                    
                    # 检查是否完成
                    total_processed = task.downloaded_images + task.failed_images
                    if total_processed >= task.total_images:
                        break
                    
                    time.sleep(1)  # 每秒检查一次
                    
                except Exception as e:
                    self.logger.error(f"监控任务时发生错误: {e}")
                    time.sleep(5)
            
            # 任务完成处理
            self._finalize_task(task_id)
            
        except Exception as e:
            self.logger.error(f"任务监控线程错误: {e}", exc_info=True)
    
    def _finalize_task(self, task_id: str):
        """完成任务处理"""
        try:
            task = self.active_tasks.get(task_id)
            task_manager = self.task_managers.get(task_id)
            
            if not task or not task_manager:
                return
            
            # 获取最终统计
            stats = task_manager.get_download_stats()
            task.downloaded_images = stats.get('downloaded_images', 0)
            task.failed_images = stats.get('failed_images', 0)
            task.downloaded_size = stats.get('downloaded_size', 0)
            
            # 更新最终状态
            if task.failed_images == 0:
                task.status = TaskStatus.COMPLETED
                self.logger.info(f"任务完成: {task.name}, 成功下载 {task.downloaded_images} 张图片")
            else:
                task.status = TaskStatus.COMPLETED  # 部分完成也算完成
                self.logger.warning(f"任务完成: {task.name}, 成功 {task.downloaded_images} 张, 失败 {task.failed_images} 张")
            
            # 停止下载管理器
            task_manager.stop()
            
            # 清理资源
            if task_id in self.task_managers:
                del self.task_managers[task_id]
            
        except Exception as e:
            self.logger.error(f"完成任务处理时发生错误: {e}", exc_info=True)
    
    def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """获取任务状态"""
        return self.active_tasks.get(task_id)
    
    def get_task_manager(self, task_id: str) -> Optional[EnhancedDownloadManager]:
        """获取任务的下载管理器"""
        return self.task_managers.get(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        try:
            task = self.active_tasks.get(task_id)
            task_manager = self.task_managers.get(task_id)
            
            if task:
                task.status = TaskStatus.CANCELLED
            
            if task_manager:
                task_manager.stop()
                del self.task_managers[task_id]
            
            self.logger.info(f"任务已取消: {task_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"取消任务失败: {e}")
            return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        try:
            task_manager = self.task_managers.get(task_id)
            if task_manager:
                task_manager.stop()
                self.logger.info(f"任务已暂停: {task_id}")
                return True
            return False
        except Exception as e:
            self.logger.error(f"暂停任务失败: {e}")
            return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        try:
            task = self.active_tasks.get(task_id)
            if not task:
                return False
            
            # 重新启动任务
            return self.start_download_task(task)
            
        except Exception as e:
            self.logger.error(f"恢复任务失败: {e}")
            return False
    
    def get_all_active_tasks(self) -> List[DownloadTask]:
        """获取所有活跃任务"""
        return list(self.active_tasks.values())
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止所有任务
            for task_id in list(self.task_managers.keys()):
                self.cancel_task(task_id)
            
            # 清理状态
            self.active_tasks.clear()
            self.task_managers.clear()
            
            self.logger.info("下载系统集成器已清理")
            
        except Exception as e:
            self.logger.error(f"清理资源时发生错误: {e}")


# 全局集成器实例
_global_integrator: Optional[DownloadSystemIntegrator] = None


def get_download_integrator(file_manager=None) -> DownloadSystemIntegrator:
    """获取全局下载系统集成器"""
    global _global_integrator
    
    if _global_integrator is None:
        _global_integrator = DownloadSystemIntegrator(file_manager)
    
    return _global_integrator


def create_enhanced_progress_window(parent, task: DownloadTask, scheduler=None):
    """创建增强版进度窗口"""
    try:
        # 导入增强版进度窗口
        from src.gui.enhanced_progress_window import EnhancedProgressWindow
        
        # 获取集成器和下载管理器
        integrator = get_download_integrator()
        download_manager = integrator.get_task_manager(task.id)
        
        # 创建进度窗口
        progress_window = EnhancedProgressWindow(
            parent=parent,
            task=task,
            scheduler=scheduler,
            download_manager=download_manager
        )
        
        return progress_window
        
    except Exception as e:
        print(f"创建增强版进度窗口失败: {e}")
        # 回退到原版进度窗口
        try:
            from src.gui.progress_window import ProgressWindow
            return ProgressWindow(parent, task, scheduler)
        except Exception as e2:
            print(f"创建原版进度窗口也失败: {e2}")
            return None


def integrate_with_existing_system():
    """与现有系统集成"""
    try:
        # 创建默认配置文件
        from src.core.download_optimization_config import create_default_config_file
        create_default_config_file()
        
        print("下载优化系统集成完成")
        print("主要改进:")
        print("1. 实时状态更新 - 进度窗口将显示实际下载状态")
        print("2. 性能优化 - 提升下载速度和并发处理能力")
        print("3. 分片下载 - 大文件支持并行分片下载")
        print("4. 自适应线程 - 根据网络状况自动调整线程数")
        print("5. 增强监控 - 详细的性能监控和错误报告")
        
        return True
        
    except Exception as e:
        print(f"系统集成失败: {e}")
        return False


if __name__ == "__main__":
    integrate_with_existing_system()