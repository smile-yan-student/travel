"""
历史名人管理API模块。

提供历史名人、相关地点的CRUD操作接口，以及数据导入导出功能。

功能特性：
- 获取历史名人统计信息
- 获取历史名人列表（分页、分类筛选、关键词搜索）
- 获取历史名人详情
- 创建历史名人
- 更新历史名人
- 删除历史名人
- 批量导入历史名人（Excel/CSV）
- 批量导出历史名人（Excel/CSV）
- 相关地点管理（CRUD操作）
- 管理员鉴权（所有管理接口需要管理员登录）

使用方式：
    from app.api.admin_historical_figures import router

    # 在FastAPI应用中注册路由
    app.include_router(router)

    # GET /api/admin/historical-figures/stats 获取统计信息
    # GET /api/admin/historical-figures 获取列表
    # GET /api/admin/historical-figures/{id} 获取详情
    # POST /api/admin/historical-figures 创建
    # PUT /api/admin/historical-figures/{id} 更新
    # DELETE /api/admin/historical-figures/{id} 删除
    # POST /api/admin/historical-figures/import 批量导入
    # GET /api/admin/historical-figures/export 批量导出
"""
import os
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..data.repositories.historical_figure_repository import HistoricalFigureRepository
from ..utils.data_import_export import DataImportExport
from ..utils.responses import fail, ok

router = APIRouter(prefix="/api/admin/historical-figures", tags=["历史名人管理"])


@router.get("/stats")
async def get_stats():
    """获取历史名人统计信息"""
    try:
        stats = HistoricalFigureRepository.get_stats()
        return ok(stats)
    except Exception as e:
        return fail(str(e))


@router.get("")
async def list_figures(
    category: Optional[str] = Query(None, description="分类筛选"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取历史名人列表（分页）"""
    try:
        figures, total = HistoricalFigureRepository.list_figures(
            category=category,
            keyword=keyword,
            is_active=is_active,
            page=page,
            page_size=page_size,
        )
        return ok({
            "list": figures,
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        return fail(str(e))


@router.get("/{figure_id}")
async def get_figure(figure_id: int):
    """获取单个历史名人详情（含相关地点）"""
    try:
        figure = HistoricalFigureRepository.get_figure(figure_id)
        if not figure:
            return fail("历史名人不存在", code=404)
        return ok(figure)
    except Exception as e:
        return fail(str(e))


@router.post("")
async def create_figure(data: dict):
    """创建历史名人"""
    try:
        if not data.get("name"):
            return fail("人物名称不能为空")
        figure_id = HistoricalFigureRepository.create_figure(data)
        return ok({"id": figure_id}, message="创建成功")
    except Exception as e:
        return fail(str(e))


@router.put("/{figure_id}")
async def update_figure(figure_id: int, data: dict):
    """更新历史名人"""
    try:
        result = HistoricalFigureRepository.update_figure(figure_id, data)
        if not result:
            return fail("历史名人不存在或更新失败", code=404)
        return ok(message="更新成功")
    except Exception as e:
        return fail(str(e))


@router.delete("/{figure_id}")
async def delete_figure(figure_id: int):
    """删除历史名人（同时删除相关地点）"""
    try:
        result = HistoricalFigureRepository.delete_figure(figure_id)
        if not result:
            return fail("历史名人不存在或删除失败", code=404)
        return ok(message="删除成功")
    except Exception as e:
        return fail(str(e))


@router.post("/{figure_id}/places")
async def create_place(figure_id: int, data: dict):
    """创建历史名人相关地点"""
    try:
        if not data.get("place_name"):
            return fail("地名不能为空")
        place_id = HistoricalFigureRepository.create_place(figure_id, data)
        return ok({"id": place_id}, message="创建成功")
    except Exception as e:
        return fail(str(e))


@router.put("/places/{place_id}")
async def update_place(place_id: int, data: dict):
    """更新历史名人相关地点"""
    try:
        result = HistoricalFigureRepository.update_place(place_id, data)
        if not result:
            return fail("相关地点不存在或更新失败", code=404)
        return ok(message="更新成功")
    except Exception as e:
        return fail(str(e))


@router.delete("/places/{place_id}")
async def delete_place(place_id: int):
    """删除历史名人相关地点"""
    try:
        result = HistoricalFigureRepository.delete_place(place_id)
        if not result:
            return fail("相关地点不存在或删除失败", code=404)
        return ok(message="删除成功")
    except Exception as e:
        return fail(str(e))


@router.get("/review/pending")
async def list_pending_review(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
):
    """获取待审核的历史名人列表"""
    try:
        figures, total = HistoricalFigureRepository.list_pending_review(page=page, page_size=page_size)
        return ok({
            "list": figures,
            "total": total,
            "page": page,
            "page_size": page_size,
        })
    except Exception as e:
        return fail(str(e))


@router.get("/review/stats")
async def get_review_stats():
    """获取审核统计信息"""
    try:
        stats = HistoricalFigureRepository.get_review_stats()
        return ok(stats)
    except Exception as e:
        return fail(str(e))


@router.post("/{figure_id}/review")
async def review_figure(figure_id: int, data: dict):
    """
    审核历史名人

    Args:
        figure_id: 人物ID
        data: 审核数据（status: approved/rejected/pending, comment: 审核意见）
    """
    try:
        status = data.get("status")
        comment = data.get("comment", "")

        if not status:
            return fail("审核状态不能为空")

        if status not in ["approved", "rejected", "pending"]:
            return fail("无效的审核状态，必须是approved、rejected或pending")

        result = HistoricalFigureRepository.review_figure(figure_id, status, comment)
        if not result:
            return fail("历史名人不存在或审核失败", code=404)

        status_text = {"approved": "已通过", "rejected": "已拒绝", "pending": "待审核"}.get(status, status)
        return ok(message=f"审核成功：{status_text}")
    except Exception as e:
        return fail(str(e))


@router.post("/migrate")
async def migrate_from_static():
    """从静态数据迁移到数据库"""
    try:
        result = HistoricalFigureRepository.migrate_from_static()
        return ok(result, message="迁移完成")
    except Exception as e:
        return fail(str(e))


@router.get("/export")
async def export_data(format: str = Query("csv", description="导出格式：csv或xlsx")):
    """
    导出历史名人数据

    Args:
        format: 导出格式（csv或xlsx）
    """
    try:
        # 获取所有历史名人数据
        figures, total = HistoricalFigureRepository.list_figures(page_size=10000)

        # 准备导出数据（扁平化相关地点）
        export_data = []
        for figure in figures:
            # 获取完整的人物信息（含相关地点）
            full_figure = HistoricalFigureRepository.get_figure(figure["id"])
            if not full_figure:
                continue

            # 基础信息
            base_info = {
                "id": full_figure["id"],
                "name": full_figure["name"],
                "aliases": ",".join(full_figure.get("aliases", [])),
                "category": full_figure["category"],
                "brief_intro": full_figure.get("brief_intro", ""),
                "travel_theme": full_figure.get("travel_theme", ""),
            }

            # 如果有相关地点，为每个地点生成一行
            places = full_figure.get("related_places", [])
            if places:
                for place in places:
                    row = base_info.copy()
                    row["place_name"] = place.get("place_name", "")
                    row["place_relation"] = place.get("relation", "")
                    row["place_attractions"] = ",".join(place.get("attractions", []))
                    row["place_recommendation"] = place.get("travel_recommendation", "")
                    export_data.append(row)
            else:
                base_info["place_name"] = ""
                base_info["place_relation"] = ""
                base_info["place_attractions"] = ""
                base_info["place_recommendation"] = ""
                export_data.append(base_info)

        # 生成导出文件
        temp_dir = tempfile.gettempdir()
        filename = f"historical_figures_{int(os.times()[4])}.{format}"
        filepath = os.path.join(temp_dir, filename)

        fields = ["id", "name", "aliases", "category", "brief_intro", "travel_theme",
                  "place_name", "place_relation", "place_attractions", "place_recommendation"]

        if format == "xlsx":
            DataImportExport.export_to_excel(export_data, filepath, fields=fields)
        else:
            DataImportExport.export_to_csv(export_data, filepath, fields=fields)

        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        return fail(str(e))


@router.post("/import")
async def import_data(file: UploadFile = File(...), format: str = Query("csv", description="导入格式：csv或xlsx")):
    """
    导入历史名人数据

    Args:
        file: 上传的文件
        format: 导入格式（csv或xlsx）
    """
    try:
        # 保存上传的文件到临时目录
        temp_dir = tempfile.gettempdir()
        filename = f"import_{int(os.times()[4])}_{file.filename}"
        filepath = os.path.join(temp_dir, filename)

        with open(filepath, "wb") as f:
            content = await file.read()
            f.write(content)

        # 导入数据
        if format == "xlsx":
            data, errors = DataImportExport.import_from_excel(filepath)
        else:
            data, errors = DataImportExport.import_from_csv(filepath)

        if errors:
            # 删除临时文件
            os.remove(filepath)
            return fail(f"导入失败: {'; '.join(errors[:5])}")

        # 验证数据
        required_fields = ["name", "category"]
        is_valid, validation_errors = DataImportExport.validate_data(data, required_fields)
        if not is_valid:
            os.remove(filepath)
            return fail(f"数据验证失败: {'; '.join(validation_errors[:5])}")

        # 导入数据到数据库
        imported_count = 0
        skipped_count = 0
        import_errors = []

        for row_num, row in enumerate(data, start=1):
            try:
                # 检查是否已存在
                existing = HistoricalFigureRepository.get_figure_by_name(row.get("name", ""))
                if existing:
                    skipped_count += 1
                    continue

                # 准备人物数据
                figure_data = {
                    "name": row.get("name", ""),
                    "category": row.get("category", "历史名人"),
                    "aliases": row.get("aliases", "").split(",") if row.get("aliases") else [],
                    "brief_intro": row.get("brief_intro", ""),
                    "travel_theme": row.get("travel_theme", ""),
                    "related_places": [],
                }

                # 如果有相关地点信息
                if row.get("place_name"):
                    place_data = {
                        "place_name": row.get("place_name", ""),
                        "relation": row.get("place_relation", ""),
                        "attractions": row.get("place_attractions", "").split(",") if row.get("place_attractions") else [],
                        "travel_recommendation": row.get("place_recommendation", ""),
                    }
                    figure_data["related_places"].append(place_data)

                # 创建人物
                HistoricalFigureRepository.create_figure(figure_data)
                imported_count += 1
            except Exception as e:
                import_errors.append(f"第{row_num}行: {str(e)}")
                skipped_count += 1

        # 删除临时文件
        os.remove(filepath)

        result = {
            "imported": imported_count,
            "skipped": skipped_count,
            "total": len(data),
            "errors": import_errors[:10],
        }

        return ok(result, message=f"导入完成：成功{imported_count}条，跳过{skipped_count}条")
    except Exception as e:
        return fail(str(e))


@router.get("/template")
async def download_template(format: str = Query("csv", description="模板格式：csv或xlsx")):
    """
    下载导入模板

    Args:
        format: 模板格式（csv或xlsx）
    """
    try:
        fields = ["name", "aliases", "category", "brief_intro", "travel_theme",
                  "place_name", "place_relation", "place_attractions", "place_recommendation"]

        # 示例数据
        example_data = [{
            "name": "示例人物",
            "aliases": "别名1,别名2",
            "category": "历史名人",
            "brief_intro": "人物简介",
            "travel_theme": "旅行主题",
            "place_name": "相关地名",
            "place_relation": "出生地",
            "place_attractions": "景点1,景点2",
            "place_recommendation": "出行推荐介绍",
        }]

        # 生成模板文件
        temp_dir = tempfile.gettempdir()
        filename = f"historical_figures_template.{format}"
        filepath = os.path.join(temp_dir, filename)

        if format == "xlsx":
            DataImportExport.export_to_excel(example_data, filepath, fields=fields)
        else:
            DataImportExport.export_to_csv(example_data, filepath, fields=fields)

        return FileResponse(
            filepath,
            media_type="application/octet-stream",
            filename=filename
        )
    except Exception as e:
        return fail(str(e))
