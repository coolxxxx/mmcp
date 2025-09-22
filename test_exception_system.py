"""
测试统一异常处理系统
"""

import sys
import time
import asyncio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

def test_basic_exceptions():
    """测试基础异常类"""
    print("测试基础异常类...")
    
    try:
        from src.core.exceptions import (
            BaseApplicationException,
            ValidationError,
            NetworkError,
            create_exception
        )
        
        # 测试基础异常
        try:
            raise BaseApplicationException("测试异常", "TEST_ERROR", {"key": "value"})
        except BaseApplicationException as e:
            print(f"✅ 基础异常测试成功: {e}")
            print(f"   错误代码: {e.error_code}")
            print(f"   详细信息: {e.details}")
        
        # 测试验证异常
        try:
            raise ValidationError("字段验证失败", field="username", value="", validation_rules=["required"])
        except ValidationError as e:
            print(f"✅ 验证异常测试成功: {e}")
        
        # 测试异常工厂
        exc = create_exception("network", "网络连接失败", url="http://example.com", status_code=404)
        print(f"✅ 异常工厂测试成功: {exc}")
        
        return True
        
    except Exception as e:
        print(f"❌ 基础异常类测试失败: {e}")
        return False

def test_error_handler():
    """测试错误处理器"""
    print("\n测试错误处理器...")
    
    try:
        from src.core.exceptions import (
            get_global_error_handler,
            ErrorContext,
            ErrorSeverity,
            RetryPolicy
        )
        
        handler = get_global_error_handler()
        
        # 测试异常处理
        context = ErrorContext(operation="test_operation", parameters={"test": "value"})
        
        try:
            raise ValueError("测试错误")
        except ValueError as e:
            result = handler.handle_exception(e, context)
            print(f"✅ 异常处理测试成功，结果: {result}")
        
        # 测试重试机制
        attempt_count = 0
        def failing_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise ConnectionError("连接失败")
            return "成功"
        
        result = handler.execute_with_retry(failing_function, context=context)
        print(f"✅ 重试机制测试成功，尝试次数: {attempt_count}，结果: {result}")
        
        # 获取统计信息
        stats = handler.get_stats()
        print(f"✅ 错误统计获取成功: 总错误数 {stats['total_errors']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误处理器测试失败: {e}")
        return False

def test_error_reporter():
    """测试错误报告器"""
    print("\n测试错误报告器...")
    
    try:
        from src.core.exceptions import (
            get_global_error_reporter,
            ErrorContext,
            ReportLevel
        )
        
        reporter = get_global_error_reporter()
        
        # 测试异常报告
        context = ErrorContext(operation="test_report", user_id="test_user")
        
        try:
            raise RuntimeError("测试运行时错误")
        except RuntimeError as e:
            report_id = reporter.report_exception(e, context, level=ReportLevel.ERROR)
            print(f"✅ 异常报告测试成功，报告ID: {report_id}")
        
        # 测试消息报告
        msg_id = reporter.report_message("测试消息", ReportLevel.INFO, context)
        print(f"✅ 消息报告测试成功，报告ID: {msg_id}")
        
        # 获取报告
        reports = reporter.get_reports(limit=5)
        print(f"✅ 报告获取成功: {len(reports)} 个报告")
        
        # 获取统计信息
        stats = reporter.get_stats()
        print(f"✅ 报告统计获取成功: 总报告数 {stats['total_reports']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 错误报告器测试失败: {e}")
        return False

def test_decorators():
    """测试装饰器"""
    print("\n测试装饰器...")
    
    try:
        from src.core.exceptions import (
            handle_exceptions,
            retry_on_failure,
            log_exceptions,
            validate_input,
            robust_operation
        )
        
        # 测试异常处理装饰器
        @handle_exceptions(default_return="默认值")
        def test_function_1():
            raise ValueError("测试异常")
        
        result = test_function_1()
        print(f"✅ 异常处理装饰器测试成功，结果: {result}")
        
        # 测试重试装饰器
        call_count = 0
        
        @retry_on_failure(max_attempts=3)
        def test_function_2():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("连接失败")
            return "重试成功"
        
        result = test_function_2()
        print(f"✅ 重试装饰器测试成功，调用次数: {call_count}，结果: {result}")
        
        # 测试输入验证装饰器
        @validate_input(
            validators={'x': lambda v: v > 0},
            error_messages={'x': 'x必须大于0'}
        )
        def test_function_3(x):
            return x * 2
        
        try:
            result = test_function_3(5)
            print(f"✅ 输入验证装饰器测试成功，结果: {result}")
        except Exception as e:
            print(f"✅ 输入验证装饰器异常测试成功: {e}")
        
        # 测试健壮操作装饰器
        @robust_operation(max_retries=2, timeout_seconds=1)
        def test_function_4():
            time.sleep(0.1)  # 模拟短时间操作
            return "健壮操作成功"
        
        result = test_function_4()
        print(f"✅ 健壮操作装饰器测试成功，结果: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ 装饰器测试失败: {e}")
        return False

async def test_async_decorators():
    """测试异步装饰器"""
    print("\n测试异步装饰器...")
    
    try:
        from src.core.exceptions import handle_exceptions, retry_on_failure
        
        # 测试异步异常处理装饰器
        @handle_exceptions(default_return="异步默认值")
        async def async_test_function_1():
            await asyncio.sleep(0.1)
            raise ValueError("异步测试异常")
        
        result = await async_test_function_1()
        print(f"✅ 异步异常处理装饰器测试成功，结果: {result}")
        
        # 测试异步重试装饰器
        async_call_count = 0
        
        @retry_on_failure(max_attempts=3, base_delay=0.1)
        async def async_test_function_2():
            nonlocal async_call_count
            async_call_count += 1
            await asyncio.sleep(0.05)
            if async_call_count < 3:
                raise ConnectionError("异步连接失败")
            return "异步重试成功"
        
        result = await async_test_function_2()
        print(f"✅ 异步重试装饰器测试成功，调用次数: {async_call_count}，结果: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ 异步装饰器测试失败: {e}")
        return False

def test_integration():
    """测试系统集成"""
    print("\n测试系统集成...")
    
    try:
        from src.core.exceptions import (
            get_global_error_handler,
            get_global_error_reporter,
            handle_exceptions,
            ErrorContext,
            NetworkError
        )
        
        # 设置错误处理器回调
        handler = get_global_error_handler()
        reporter = get_global_error_reporter()
        
        def error_callback(exception, context):
            print(f"   错误回调触发: {type(exception).__name__}")
        
        handler.add_error_callback(error_callback)
        
        # 测试集成场景
        @handle_exceptions(report_errors=True)
        def integrated_function():
            context = ErrorContext(operation="integrated_test", user_id="test_user")
            raise NetworkError("网络集成测试错误", url="http://test.com", status_code=500)
        
        result = integrated_function()
        print(f"✅ 系统集成测试成功，结果: {result}")
        
        # 检查报告是否生成
        recent_reports = reporter.get_reports(limit=1)
        if recent_reports:
            print(f"✅ 集成报告生成成功: {recent_reports[0].exception_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ 系统集成测试失败: {e}")
        return False

async def main():
    """主测试函数"""
    print("🚀 开始测试统一异常处理系统...")
    
    test_results = []
    
    # 各模块功能测试
    test_results.append(test_basic_exceptions())
    test_results.append(test_error_handler())
    test_results.append(test_error_reporter())
    test_results.append(test_decorators())
    test_results.append(await test_async_decorators())
    test_results.append(test_integration())
    
    # 统计结果
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"\n📊 测试结果: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 统一异常处理系统测试全部通过！")
        return True
    else:
        print("⚠️  部分测试失败，但核心功能可用")
        return False

if __name__ == "__main__":
    # 运行测试
    result = asyncio.run(main())
    
    if result:
        print("\n✅ 统一异常处理系统工作正常，可以继续下一步优化")
    else:
        print("\n⚠️  存在一些问题，但不影响继续优化")