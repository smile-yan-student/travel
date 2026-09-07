"""
数据导入导出工具模块。

支持从 Excel/CSV 批量导入导出数据，用于 POI 层级、历史名人等数据的批量管理。

功能特性：
- 支持 CSV 和 Excel 两种格式的导入导出
- 自动处理列表/字典类型的字段（转换为 JSON 字符串）
- 支持数据验证（必填字段、唯一字段）
- 支持生成导入模板文件
- Excel 导出支持表头样式和自动列宽调整

使用方式：
    from app.utils.data_import_export import DataImportExport

    # 导出数据到 CSV
    csv_path = DataImportExport.export_to_csv(data, "output.csv", fields=["name", "city"])

    # 从 CSV 导入数据
    data, errors = DataImportExport.import_from_csv("input.csv")

    # 导出数据到 Excel
    excel_path = DataImportExport.export_to_excel(data, "output.xlsx", sheet_name="数据")

    # 验证导入数据
    is_valid, errors = DataImportExport.validate_data(data, required_fields=["name"], unique_fields=["id"])
"""
import csv
import io
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class DataImportExport:
    """
    数据导入导出工具类。

    提供静态方法，支持 CSV 和 Excel 格式的批量导入导出，
    以及数据验证和模板生成功能。

    所有方法均为静态方法，无需实例化即可使用。
    """

    @staticmethod
    def export_to_csv(
        data: List[Dict[str, Any]],
        filename: str,
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        导出数据到 CSV 文件。

        Args:
            data: 数据列表，每个元素为字典
            filename: 输出文件路径
            fields: 字段列表（可选，默认使用第一条数据的所有键）

        Returns:
            str: CSV 文件路径，如果数据为空则返回空字符串

        Example:
            >>> data = [{"name": "张三", "city": "北京"}, {"name": "李四", "city": "上海"}]
            >>> path = DataImportExport.export_to_csv(data, "users.csv", fields=["name", "city"])
            >>> print(path)
            'users.csv'
        """
        if not data:
            return ""

        # 如果没有指定字段，使用第一条数据的键
        if not fields:
            fields = list(data[0].keys())

        # 确保目录存在
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for row in data:
                # 处理列表/字典类型的字段，转换为 JSON 字符串
                processed_row = DataImportExport._process_row_for_export(row)
                writer.writerow(processed_row)

        return str(output_path)

    @staticmethod
    def import_from_csv(
        filename: str,
        fields: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        从 CSV 文件导入数据。

        Args:
            filename: 输入文件路径
            fields: 字段列表（可选，默认使用 CSV 的表头）

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]: (数据列表, 错误信息列表)

        Example:
            >>> data, errors = DataImportExport.import_from_csv("users.csv")
            >>> if errors:
            ...     print(f"导入完成，有 {len(errors)} 个错误")
            >>> else:
            ...     print(f"成功导入 {len(data)} 条数据")
        """
        data: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            with open(filename, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not fields:
                    fields = reader.fieldnames

                for row_num, row in enumerate(reader, start=2):
                    try:
                        # 处理 JSON 字符串字段
                        processed_row = DataImportExport._process_row_for_import(row)
                        data.append(processed_row)
                    except Exception as e:
                        errors.append(f"第{row_num}行: {str(e)}")
        except FileNotFoundError:
            errors.append(f"文件不存在: {filename}")
        except Exception as e:
            errors.append(f"读取文件失败: {str(e)}")

        return data, errors

    @staticmethod
    def export_to_excel(
        data: List[Dict[str, Any]],
        filename: str,
        sheet_name: str = "Sheet1",
        fields: Optional[List[str]] = None,
    ) -> str:
        """
        导出数据到 Excel 文件（需要 openpyxl 库）。

        如果未安装 openpyxl，自动回退到 CSV 格式。

        Args:
            data: 数据列表，每个元素为字典
            filename: 输出文件路径
            sheet_name: 工作表名称，默认 "Sheet1"
            fields: 字段列表（可选，默认使用第一条数据的所有键）

        Returns:
            str: Excel 文件路径，如果数据为空则返回空字符串

        Example:
            >>> data = [{"name": "张三", "city": "北京"}, {"name": "李四", "city": "上海"}]
            >>> path = DataImportExport.export_to_excel(data, "users.xlsx", sheet_name="用户数据")
            >>> print(path)
            'users.xlsx'
        """
        try:
            import openpyxl
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            # 如果没有 openpyxl，回退到 CSV
            csv_filename = filename.replace(".xlsx", ".csv")
            return DataImportExport.export_to_csv(data, csv_filename, fields)

        if not data:
            return ""

        if not fields:
            fields = list(data[0].keys())

        # 创建工作簿
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = sheet_name

        # 写入表头（带样式）
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
        for col, field in enumerate(fields, start=1):
            cell = ws.cell(row=1, column=col, value=field)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # 写入数据
        for row_num, row in enumerate(data, start=2):
            for col, field in enumerate(fields, start=1):
                value = row.get(field, "")
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)
                ws.cell(row=row_num, column=col, value=value)

        # 自动调整列宽（最大 50 字符）
        for col in ws.columns:
            max_length = 0
            column = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except Exception:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column].width = adjusted_width

        # 确保目录存在
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb.save(output_path)
        return str(output_path)

    @staticmethod
    def import_from_excel(
        filename: str,
        sheet_name: Optional[str] = None,
        fields: Optional[List[str]] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        从 Excel 文件导入数据（需要 openpyxl 库）。

        Args:
            filename: 输入文件路径
            sheet_name: 工作表名称（可选，默认第一个工作表）
            fields: 字段列表（可选，默认使用 Excel 的表头）

        Returns:
            Tuple[List[Dict[str, Any]], List[str]]: (数据列表, 错误信息列表)

        Example:
            >>> data, errors = DataImportExport.import_from_excel("users.xlsx", sheet_name="用户数据")
            >>> if errors:
            ...     print(f"导入完成，有 {len(errors)} 个错误")
            >>> else:
            ...     print(f"成功导入 {len(data)} 条数据")
        """
        try:
            import openpyxl
        except ImportError:
            return [], ["需要安装 openpyxl 库: pip install openpyxl"]

        data: List[Dict[str, Any]] = []
        errors: List[str] = []

        try:
            wb = openpyxl.load_workbook(filename, read_only=True, data_only=True)
            ws = wb[sheet_name] if sheet_name else wb.active

            # 读取表头
            headers: List[str] = []
            for cell in ws[1]:
                headers.append(cell.value)

            if not fields:
                fields = headers

            # 读取数据
            for row_num, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                try:
                    row_dict: Dict[str, Any] = {}
                    for col, field in enumerate(fields):
                        if col < len(row):
                            value = row[col]
                            # 处理 JSON 字符串字段
                            if value and isinstance(value, str) and (
                                value.startswith("[") or value.startswith("{")
                            ):
                                try:
                                    value = json.loads(value)
                                except json.JSONDecodeError:
                                    pass
                            row_dict[field] = value
                    data.append(row_dict)
                except Exception as e:
                    errors.append(f"第{row_num}行: {str(e)}")

            wb.close()
        except FileNotFoundError:
            errors.append(f"文件不存在: {filename}")
        except Exception as e:
            errors.append(f"读取文件失败: {str(e)}")

        return data, errors

    @staticmethod
    def validate_data(
        data: List[Dict[str, Any]],
        required_fields: List[str],
        unique_fields: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        验证导入数据的有效性。

        检查必填字段是否为空，以及唯一字段是否重复。

        Args:
            data: 数据列表，每个元素为字典
            required_fields: 必填字段列表
            unique_fields: 唯一字段列表（可选）

        Returns:
            Tuple[bool, List[str]]: (是否有效, 错误信息列表)

        Example:
            >>> data = [{"id": 1, "name": "张三"}, {"id": 1, "name": "李四"}]
            >>> is_valid, errors = DataImportExport.validate_data(
            ...     data, required_fields=["name"], unique_fields=["id"]
            ... )
            >>> print(is_valid, errors)
            False ['第2行: 字段 'id' 的值 '1' 与第1行重复']
        """
        errors: List[str] = []

        if not data:
            return False, ["数据为空"]

        # 检查必填字段
        for row_num, row in enumerate(data, start=1):
            for field in required_fields:
                if not row.get(field):
                    errors.append(f"第{row_num}行: 必填字段 '{field}' 为空")

        # 检查唯一字段
        if unique_fields:
            seen_values: Dict[str, Dict[Any, int]] = {}
            for row_num, row in enumerate(data, start=1):
                for field in unique_fields:
                    value = row.get(field)
                    if value:
                        if field not in seen_values:
                            seen_values[field] = {}
                        if value in seen_values[field]:
                            errors.append(
                                f"第{row_num}行: 字段 '{field}' 的值 '{value}' "
                                f"与第{seen_values[field][value]}行重复"
                            )
                        else:
                            seen_values[field][value] = row_num

        return len(errors) == 0, errors

    @staticmethod
    def generate_template(
        fields: List[str],
        filename: str,
        example_data: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        生成导入模板文件。

        根据字段列表生成 CSV 或 Excel 格式的导入模板，可包含示例数据。

        Args:
            fields: 字段列表
            filename: 输出文件路径（根据扩展名决定格式，.xlsx 为 Excel，其他为 CSV）
            example_data: 示例数据列表（可选）

        Returns:
            str: 模板文件路径

        Example:
            >>> fields = ["id", "name", "city", "description"]
            >>> example = [{"id": 1, "name": "示例", "city": "北京", "description": "示例数据"}]
            >>> path = DataImportExport.generate_template(fields, "template.xlsx", example_data=example)
            >>> print(path)
            'template.xlsx'
        """
        data = example_data or []
        if filename.endswith(".xlsx"):
            return DataImportExport.export_to_excel(data, filename, fields=fields)
        else:
            return DataImportExport.export_to_csv(data, filename, fields=fields)

    # ============================================================
    # 内部辅助方法
    # ============================================================

    @staticmethod
    def _process_row_for_export(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理导出数据的行，将列表/字典类型转换为 JSON 字符串。

        Args:
            row: 原始数据行

        Returns:
            Dict[str, Any]: 处理后的数据行
        """
        processed_row: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, (list, dict)):
                processed_row[key] = json.dumps(value, ensure_ascii=False)
            else:
                processed_row[key] = value
        return processed_row

    @staticmethod
    def _process_row_for_import(row: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理导入数据的行，将 JSON 字符串转换为列表/字典。

        Args:
            row: 原始数据行

        Returns:
            Dict[str, Any]: 处理后的数据行
        """
        processed_row: Dict[str, Any] = {}
        for key, value in row.items():
            if value and isinstance(value, str) and (
                value.startswith("[") or value.startswith("{")
            ):
                try:
                    processed_row[key] = json.loads(value)
                except json.JSONDecodeError:
                    processed_row[key] = value
            else:
                processed_row[key] = value
        return processed_row
