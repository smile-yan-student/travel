# 代码风格规范（Code Style Guide）

> 本文档定义了本项目的代码风格规范，参考 caasm_server 项目的编码风格，结合 Python 社区最佳实践（PEP 8、PEP 257、PEP 484 等）制定。
>
> 所有新代码必须遵循本规范，现有代码应逐步重构以符合本规范。

## 目录

1. [命名规范](#1-命名规范)
2. [类型注解规范](#2-类型注解规范)
3. [文档字符串规范](#3-文档字符串规范)
4. [代码组织规范](#4-代码组织规范)
5. [注释规范](#5-注释规范)
6. [导入规范](#6-导入规范)
7. [异常处理规范](#7-异常处理规范)
8. [配置管理规范](#8-配置管理规范)
9. [日志规范](#9-日志规范)
10. [测试规范](#10-测试规范)

---

## 1. 命名规范

### 1.1 通用原则

- 使用英文命名，禁止使用拼音或中文
- 命名应具有描述性，避免使用缩写（除非是广泛认可的缩写）
- 命名长度应适中，既不要过短（如 `a`, `b`, `x`），也不要过长（超过 50 个字符）

### 1.2 文件和模块

- **文件名**：使用小写蛇形命名（`snake_case`），如 `user_service.py`, `param_validator.py`
- **模块名**：与文件名一致，使用小写蛇形命名
- **包名**：使用小写蛇形命名，如 `app.services`, `app.api`

### 1.3 类

- **类名**：使用大驼峰命名（`PascalCase`），如 `UserService`, `ParameterValidator`
- **异常类名**：以 `Error` 或 `Exception` 结尾，如 `ValidationError`, `ConfigException`
- **私有类**：以单下划线开头，如 `_InternalService`

### 1.4 函数和方法

- **函数名**：使用小写蛇形命名（`snake_case`），如 `get_user_by_id`, `validate_params`
- **方法名**：与函数名一致，使用小写蛇形命名
- **私有方法**：以单下划线开头，如 `_internal_method`
- **特殊方法**：以双下划线开头和结尾，如 `__init__`, `__str__`
- **布尔函数/方法**：以 `is_`, `has_`, `can_` 开头，如 `is_valid`, `has_permission`
- **返回集合的函数/方法**：以复数形式结尾，如 `get_users`, `find_attractions`

### 1.5 变量

- **变量名**：使用小写蛇形命名（`snake_case`），如 `user_name`, `total_count`
- **常量**：使用大写蛇形命名（`UPPER_SNAKE_CASE`），如 `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT`
- **私有变量**：以单下划线开头，如 `_internal_state`
- **实例变量**：在 `__init__` 中初始化，使用小写蛇形命名
- **类型变量**：使用大驼峰命名，如 `T`, `UserType`

### 1.6 其他

- **数据库表名**：使用小写蛇形命名，如 `users`, `travel_plans`
- **数据库字段名**：使用小写蛇形命名，如 `created_at`, `user_id`
- **API 路径**：使用小写连字符命名（`kebab-case`），如 `/api/v1/user-profiles`
- **环境变量**：使用大写蛇形命名，如 `DB_HOST`, `JWT_SECRET`

---

## 2. 类型注解规范

### 2.1 通用原则

- 所有公共函数和方法必须添加类型注解
- 所有公共类的属性必须添加类型注解
- 复杂类型应使用 `typing` 模块中的类型（如 `List`, `Dict`, `Optional`, `Tuple`）
- Python 3.9+ 可以使用内置类型（如 `list`, `dict`），但为了兼容性建议使用 `typing` 模块

### 2.2 函数和方法

```python
# 正确示例
def get_user_by_id(user_id: int) -> Optional[User]:
    """根据用户ID获取用户"""
    ...

def calculate_total_price(items: List[Item], discount: float = 0.0) -> float:
    """计算总价"""
    ...

def validate_params(params: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """验证参数"""
    ...

# 错误示例
def get_user_by_id(user_id):
    ...

def calculate_total_price(items, discount=0.0):
    ...
```

### 2.3 类属性

```python
# 正确示例
@dataclass
class User:
    id: int
    name: str
    email: str
    is_active: bool = True
    created_at: Optional[datetime] = None

# 错误示例
@dataclass
class User:
    id = 0
    name = ""
    email = ""
```

### 2.4 变量

```python
# 正确示例
users: List[User] = []
total_count: int = 0
is_valid: bool = False

# 对于复杂类型，建议添加类型注解
result: Dict[str, Any] = {
    "code": 200,
    "message": "success",
    "data": None,
}
```

### 2.5 返回值

- 函数必须有明确的返回值类型注解
- 如果函数没有返回值，使用 `-> None`
- 如果函数可能返回 `None`，使用 `Optional[T]`
- 如果函数返回多个值，使用 `Tuple[T1, T2, ...]`

---

## 3. 文档字符串规范

### 3.1 通用原则

- 所有公共模块、类、函数和方法必须添加文档字符串
- 文档字符串使用三引号（`"""`），不使用单引号（`'''`）
- 文档字符串应简洁明了，描述"做什么"，而不是"怎么做"
- 文档字符串应包含参数、返回值、异常等信息

### 3.2 模块文档字符串

```python
"""
模块名称

模块功能描述，简要说明本模块的作用和主要功能。

使用方式：
    from app.module import ClassName
    
    instance = ClassName()
    result = instance.method()

包含：
- 功能1描述
- 功能2描述
- 功能3描述
"""
```

### 3.3 类文档字符串

```python
class UserService:
    """
    用户服务类

    提供用户相关的业务逻辑，包括用户创建、查询、更新、删除等功能。

    属性：
        db: 数据库连接
        cache: 缓存客户端

    使用方式：
        service = UserService(db, cache)
        user = service.get_user_by_id(1)
    """

    def __init__(self, db: Database, cache: CacheClient):
        """初始化用户服务"""
        self.db = db
        self.cache = cache
```

### 3.4 函数和方法文档字符串

```python
def get_user_by_id(user_id: int) -> Optional[User]:
    """
    根据用户ID获取用户

    Args:
        user_id: 用户ID，必须为正整数

    Returns:
        Optional[User]: 用户对象，如果不存在则返回None

    Raises:
        ValueError: 当user_id无效时抛出
        DatabaseError: 当数据库查询失败时抛出

    Example:
        >>> user = get_user_by_id(1)
        >>> print(user.name)
        '张三'
    """
    ...
```

### 3.5 文档字符串格式

- 使用 Google 风格的文档字符串（Args, Returns, Raises, Example）
- 参数描述应包含参数的含义和约束
- 返回值描述应包含返回值的类型和含义
- 异常描述应包含异常类型和触发条件
- 示例代码应简洁明了，可直接运行

---

## 4. 代码组织规范

### 4.1 文件结构

每个 Python 文件应按照以下顺序组织：

1. 模块文档字符串
2. 导入语句（标准库、第三方库、本地模块）
3. 全局常量和变量
4. 异常类定义
5. 数据类定义（`@dataclass`）
6. 枚举类定义（`Enum`）
7. 工具函数定义
8. 类定义
9. 主函数或入口代码

### 4.2 类结构

每个类应按照以下顺序组织：

1. 类文档字符串
2. 类变量和常量
3. `__init__` 方法
4. 特殊方法（`__str__`, `__repr__`, `__eq__` 等）
5. 属性方法（`@property`）
6. 公共方法
7. 私有方法（以 `_` 开头）
8. 静态方法（`@staticmethod`）
9. 类方法（`@classmethod`）

### 4.3 函数长度

- 函数长度应控制在 50 行以内（不包括文档字符串和空行）
- 如果函数超过 50 行，应考虑拆分为多个小函数
- 函数应只做一件事，遵循单一职责原则

### 4.4 类长度

- 类长度应控制在 300 行以内
- 如果类超过 300 行，应考虑拆分为多个类
- 类应只负责一个领域的功能，遵循单一职责原则

### 4.5 模块长度

- 模块长度应控制在 500 行以内
- 如果模块超过 500 行，应考虑拆分为多个模块
- 模块应只包含相关的功能，遵循高内聚低耦合原则

---

## 5. 注释规范

### 5.1 通用原则

- 注释应解释"为什么"，而不是"做什么"
- 代码本身应该是自解释的，注释只用于解释复杂的逻辑
- 注释应与代码保持同步，修改代码时应同时更新注释
- 禁止使用无意义的注释（如 `i += 1  # i加1`）

### 5.2 行内注释

- 行内注释应与代码之间至少有两个空格
- 行内注释应以 `#` 开头，后跟一个空格
- 行内注释应简洁明了，不超过一行

```python
# 正确示例
total = sum(items)  # 计算总价，包含折扣

# 错误示例
total = sum(items) #计算总价
total = sum(items)  # 把items加起来
```

### 5.3 块注释

- 块注释应缩进到与代码相同的级别
- 块注释的每一行都应以 `#` 开头，后跟一个空格
- 块注释应与代码之间用空行分隔

```python
# 正确示例
# 计算用户的总消费金额
# 包括订单金额、运费和税费
total_amount = order_amount + shipping_fee + tax

# 错误示例
#计算用户的总消费金额
#包括订单金额、运费和税费
total_amount = order_amount + shipping_fee + tax
```

### 5.4 TODO 注释

- TODO 注释应使用 `# TODO:` 格式，后跟描述
- TODO 注释应包含负责人和截止日期（如果适用）
- 应定期清理已完成的 TODO 注释

```python
# TODO: 优化查询性能，添加缓存
# TODO(张三): 修复并发问题，截止日期：2026-01-01
```

---

## 6. 导入规范

### 6.1 导入顺序

导入语句应按照以下顺序组织，每组之间用空行分隔：

1. 标准库导入（如 `os`, `sys`, `datetime`）
2. 第三方库导入（如 `fastapi`, `pydantic`, `sqlalchemy`）
3. 本地模块导入（如 `app.config`, `app.utils`）

```python
# 正确示例
import os
import sys
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.utils import get_logger
```

### 6.2 导入方式

- 使用 `from module import name` 方式导入，而不是 `import module`
- 避免使用 `from module import *`（通配符导入）
- 导入的名称应按字母顺序排列
- 如果导入的名称超过 3 个，应使用括号包裹

```python
# 正确示例
from typing import Dict, List, Optional, Tuple

# 错误示例
from typing import *
from typing import List, Dict, Optional, Tuple  # 未按字母顺序
```

### 6.3 相对导入 vs 绝对导入

- 优先使用绝对导入（如 `from app.config import settings`）
- 避免使用相对导入（如 `from ..config import settings`），除非是在包内部
- 绝对导入更清晰，更容易理解模块的位置

### 6.4 循环导入

- 避免循环导入（A 导入 B，B 导入 A）
- 如果出现循环导入，应考虑重构代码，将共享的功能提取到第三个模块
- 可以使用延迟导入（在函数内部导入）来解决循环导入问题，但应谨慎使用

---

## 7. 异常处理规范

### 7.1 通用原则

- 不要忽略异常，除非有明确的理由
- 捕获异常后应进行处理，而不是简单地 `pass`
- 异常应在合适的层级捕获和处理
- 自定义异常应继承自合适的基类

### 7.2 异常捕获

```python
# 正确示例
try:
    result = risky_operation()
except SpecificError as e:
    logger.error(f"操作失败: {e}")
    result = default_value
except Exception as e:
    logger.exception(f"未知错误: {e}")
    raise

# 错误示例
try:
    result = risky_operation()
except:
    pass  # 忽略所有异常

try:
    result = risky_operation()
except Exception:
    print("出错了")  # 没有记录详细信息
```

### 7.3 自定义异常

```python
class AppError(Exception):
    """应用基类异常"""
    def __init__(self, message: str, code: int = 500):
        self.message = message
        self.code = code
        super().__init__(message)

class ValidationError(AppError):
    """参数验证异常"""
    def __init__(self, message: str, errors: List[str] = None):
        super().__init__(message, code=400)
        self.errors = errors or []

class NotFoundError(AppError):
    """资源不存在异常"""
    def __init__(self, resource: str, resource_id: Any):
        message = f"{resource}不存在: {resource_id}"
        super().__init__(message, code=404)
```

### 7.4 异常抛出

- 抛出异常时应提供有意义的错误消息
- 错误消息应包含足够的上下文信息，便于调试
- 不要抛出过于通用的异常（如 `Exception`），应使用具体的异常类型

---

## 8. 配置管理规范

### 8.1 配置类

- 使用 `dataclass` 定义配置类
- 配置项应按功能分组（如 `AppConfig`, `DBConfig`, `AIConfig`）
- 配置项应有明确的类型注解和默认值
- 配置应从环境变量或配置文件加载

```python
@dataclass
class DBConfig:
    """数据库配置"""
    host: str = field(default_factory=lambda: _get_str("DB_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: _get_int("DB_PORT", 3306))
    user: str = field(default_factory=lambda: _get_str("DB_USER", "root"))
    password: str = field(default_factory=lambda: _get_str("DB_PASSWORD", ""))
    name: str = field(default_factory=lambda: _get_str("DB_NAME", "app"))

    @property
    def dsn(self) -> str:
        """数据库连接 DSN"""
        return f"mysql+pymysql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
```

### 8.2 配置验证

- 配置加载后应进行验证
- 验证应检查配置项的有效性（如范围、格式、依赖关系）
- 验证失败时应抛出明确的异常
- 生产环境应进行更严格的验证（如密钥强度、调试模式）

### 8.3 敏感信息

- 敏感信息（如密码、密钥）不应硬编码在代码中
- 敏感信息应从环境变量或安全的配置管理系统加载
- 日志中不应输出敏感信息
- 配置摘要中应隐藏敏感信息（如只显示是否已配置）

---

## 9. 日志规范

### 9.1 日志级别

- `DEBUG`：调试信息，用于开发和调试阶段
- `INFO`：一般信息，用于记录正常的业务流程
- `WARNING`：警告信息，用于记录可能的问题，但不影响正常运行
- `ERROR`：错误信息，用于记录影响功能的错误
- `CRITICAL`：严重错误，用于记录导致系统崩溃的错误

### 9.2 日志格式

- 日志应包含时间、级别、模块、行号、消息等信息
- 日志应使用结构化格式（如 JSON），便于后续分析
- 日志消息应简洁明了，包含足够的上下文信息

```python
# 正确示例
logger.info("用户登录成功", extra={"user_id": user.id, "ip": request.client.host})
logger.error("数据库查询失败", extra={"sql": sql, "params": params, "error": str(e)})

# 错误示例
logger.info("登录成功")  # 缺少上下文信息
logger.error(f"查询失败: {e}")  # 使用字符串拼接，不利于结构化日志
```

### 9.3 日志记录时机

- 业务流程的关键节点应记录日志（如开始、完成、失败）
- 异常应记录日志，包括异常堆栈信息
- 外部服务调用应记录日志（如请求参数、响应结果、耗时）
- 性能敏感的操作应记录耗时

### 9.4 日志安全

- 日志中不应包含敏感信息（如密码、密钥、身份证号）
- 日志中不应包含用户的隐私信息（除非有明确的业务需求）
- 生产环境的日志级别应设置为 `INFO` 或更高

---

## 10. 测试规范

### 10.1 测试原则

- 所有公共函数和方法都应有对应的测试
- 测试应覆盖正常流程、边界情况和异常情况
- 测试应独立运行，不依赖外部服务（使用 Mock）
- 测试应易于理解和维护

### 10.2 测试命名

- 测试文件应以 `test_` 开头，如 `test_user_service.py`
- 测试类应以 `Test` 开头，如 `TestUserService`
- 测试方法应以 `test_` 开头，如 `test_get_user_by_id`
- 测试方法名应描述测试的场景和预期结果

```python
class TestUserService:
    def test_get_user_by_id_with_valid_id(self):
        """测试使用有效ID获取用户"""
        ...

    def test_get_user_by_id_with_invalid_id(self):
        """测试使用无效ID获取用户"""
        ...

    def test_get_user_by_id_with_nonexistent_id(self):
        """测试使用不存在的ID获取用户"""
        ...
```

### 10.3 测试结构

- 测试应遵循 Arrange-Act-Assert (AAA) 模式
- 每个测试只测试一个功能点
- 测试应使用 fixtures 来准备测试数据
- 测试应清理测试数据，避免影响其他测试

```python
def test_create_user(self, db_session):
    # Arrange
    user_data = {
        "name": "张三",
        "email": "zhangsan@example.com",
    }

    # Act
    user = user_service.create_user(db_session, **user_data)

    # Assert
    assert user.name == "张三"
    assert user.email == "zhangsan@example.com"
    assert user.id is not None
```

---

## 附录

### A. 参考资料

- [PEP 8 -- Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 257 -- Docstring Conventions](https://peps.python.org/pep-0257/)
- [PEP 484 -- Type Hints](https://peps.python.org/pep-0484/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [caasm_server 项目编码风格](file:///Users/passenger/Downloads/Passneger/code/caasm_codes/caasm_server)

### B. 工具推荐

- 代码格式化：`black`, `autopep8`
- 代码检查：`pylint`, `flake8`, `mypy`
- 类型检查：`mypy`, `pyright`
- 测试框架：`pytest`, `unittest`
- 文档生成：`sphinx`, `pdoc`

### C. 变更记录

| 日期 | 版本 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 2026-08-30 | 1.0.0 | 初始版本，定义基础代码风格规范 | AI |
