"""
统一响应格式模块。

定义标准 API 响应格式，所有接口应使用 ApiResponse 包装返回数据，
确保前端解析一致性。

响应格式：
{
    "code": "0",           // 错误码，"0" 表示成功
    "message": "success",  // 提示信息
    "data": {...},         // 业务数据
    "trace_id": "xxx"      // 链路追踪 ID
}

使用方式：
    from app.utils.responses import ApiResponse, ok, fail, paginated

    # 方式1：使用 ApiResponse 类
    return ApiResponse.success(data=result)
    return ApiResponse.error(code="10001", message="参数错误")

    # 方式2：使用快捷函数（返回字典，可直接用于 return）
    return ok(data=result)
    return fail(code="10001", message="参数错误")
    return paginated(items=items, total=total, page=1, page_size=20)
"""
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应格式。

    所有接口应使用本类包装返回数据，确保前端解析一致性。

    属性：
        code: 错误码，"0" 表示成功
        message: 提示信息
        data: 业务数据
        trace_id: 链路追踪 ID

    使用方式：
        return ApiResponse.success(data=result)
        return ApiResponse.error(code="10001", message="参数错误")
    """

    code: str = Field(default="0", description="错误码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")
    trace_id: str = Field(default="", description="链路追踪 ID")

    @classmethod
    def success(
        cls,
        data: Any = None,
        message: str = "success",
        trace_id: str = "",
    ) -> "ApiResponse":
        """
        创建成功响应。

        Args:
            data: 业务数据
            message: 提示信息，默认为 "success"
            trace_id: 链路追踪 ID

        Returns:
            ApiResponse: 成功响应对象
        """
        return cls(code="0", message=message, data=data, trace_id=trace_id)

    @classmethod
    def error(
        cls,
        code: str = "10000",
        message: str = "操作失败",
        data: Any = None,
        trace_id: str = "",
    ) -> "ApiResponse":
        """
        创建错误响应。

        Args:
            code: 错误码，默认为 "10000"
            message: 错误提示信息
            data: 附加数据
            trace_id: 链路追踪 ID

        Returns:
            ApiResponse: 错误响应对象
        """
        return cls(code=code, message=message, data=data, trace_id=trace_id)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典（用于 JSONResponse）。

        Returns:
            Dict[str, Any]: 包含响应数据的字典
        """
        return {
            "code": self.code,
            "message": self.message,
            "data": self.data,
            "trace_id": self.trace_id,
        }


class PaginatedData(BaseModel):
    """
    分页数据包装。

    用于列表接口的统一分页格式。

    属性：
        items: 数据列表
        total: 总记录数
        page: 当前页码
        page_size: 每页条数
        has_more: 是否有更多数据
    """

    items: List[Any] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页条数")
    has_more: bool = Field(default=False, description="是否有更多数据")


def ok(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """
    快捷成功响应（返回字典，可直接用于 return）。

    Args:
        data: 业务数据
        message: 提示信息，默认为 "success"

    Returns:
        Dict[str, Any]: 成功响应字典
    """
    return ApiResponse.success(data=data, message=message).to_dict()


def fail(
    code: str = "10000",
    message: str = "操作失败",
    data: Any = None,
) -> Dict[str, Any]:
    """
    快捷错误响应（返回字典，可直接用于 return）。

    Args:
        code: 错误码，默认为 "10000"
        message: 错误提示信息
        data: 附加数据

    Returns:
        Dict[str, Any]: 错误响应字典
    """
    return ApiResponse.error(code=code, message=message, data=data).to_dict()


def paginated(
    items: List[Any],
    total: int,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """
    快捷分页响应。

    Args:
        items: 数据列表
        total: 总记录数
        page: 当前页码，默认为 1
        page_size: 每页条数，默认为 20

    Returns:
        Dict[str, Any]: 分页响应字典
    """
    has_more = (page * page_size) < total
    data = PaginatedData(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )
    return ok(data=data.model_dump())
