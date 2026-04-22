---
name: excel-merged-cell-handler
description: "Excel合并单元格处理器：检测、分析、填充合并单元格。通用工具，可复用于任何Excel解析任务。"
---

# Excel Merged Cell Handler Skill

> Excel合并单元格处理 - 检测、分析、填充

---

## 问题说明

`pandas.read_excel()` 不会保留合并单元格信息，导致：
- 合并单元格只有左上角显示值
- 其他位置变成 `NaN`
- 数据出现重复或缺失

---

## 核心功能

| 功能 | 方法 |
|------|------|
| 检测合并单元格 | `ws.merged_cells.ranges` |
| 分析合并信息 | bounds, direction, value |
| 填充合并单元格 | 自动填充左上角值 |
| 多行表头处理 | 合并列名 |

---

## Python实现

### read_excel_with_merged_cells 函数

```python
from openpyxl import load_workbook

def read_excel_with_merged_cells(file_path, sheet_name=None, header_row=0):
    wb = load_workbook(file_path, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active
    
    data = []
    for row in ws.iter_rows(values_only=True):
        data.append(list(row))
    
    # 填充合并单元格
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        
        r_start = min_row - 1
        r_end = max_row
        c_start = min_col - 1
        c_end = max_col
        
        value = data[r_start][c_start]
        
        if value is not None:
            for r in range(r_start, r_end):
                for c in range(c_start, c_end):
                    data[r][c] = value
    
    wb.close()
    return data
```

### ExcelMergedCellHandler 类

```python
class ExcelMergedCellHandler:
    def __init__(self, file_path):
        self.file_path = file_path
        self.wb = load_workbook(file_path, data_only=True)
    
    def get_merged_ranges(self, sheet_name=None):
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        ranges = []
        for merged_range in ws.merged_cells.ranges:
            ranges.append(merged_range.bounds)
        return ranges
    
    def get_merged_ranges_info(self, sheet_name=None):
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        infos = []
        for merged_range in ws.merged_cells.ranges:
            min_col, min_row, max_col, max_row = merged_range.bounds
            is_vertical = (min_col == max_col)
            is_horizontal = (min_row == max_row)
            value = ws.cell(row=min_row, column=min_col).value
            infos.append({
                'range': str(merged_range),
                'bounds': (min_col, min_row, max_col, max_row),
                'value': value,
                'is_vertical': is_vertical,
                'is_horizontal': is_horizontal,
                'height': max_row - min_row + 1,
                'width': max_col - min_col + 1
            })
        return infos
    
    def read_with_filled_merged(self, sheet_name=None):
        ws = self.wb[sheet_name] if sheet_name else self.wb.active
        data = []
        for row in ws.iter_rows(values_only=True):
            data.append(list(row))
        for merged_range in ws.merged_cells.ranges:
            min_col, min_row, max_col, max_row = merged_range.bounds
            r_start = min_row - 1
            r_end = max_row
            c_start = min_col - 1
            c_end = max_col
            value = data[r_start][c_start]
            if value is not None:
                for r in range(r_start, r_end):
                    for c in range(c_start, c_end):
                        data[r][c] = value
        return data
    
    def close(self):
        self.wb.close()
```

### parse_multirow_header 函数

```python
def parse_multirow_header(data, header_rows=2):
    headers = data[:header_rows]
    body = data[header_rows:]
    
    new_columns = []
    for col_idx in range(len(headers[0])):
        col_parts = [headers[r][col_idx] for r in range(header_rows) if headers[r][col_idx]]
        col_name = ' - '.join(str(p) for p in col_parts)
        new_columns.append(col_name if col_name else f'col_{col_idx}')
    
    return new_columns, body
```

### detect_header_rows 函数

```python
def detect_header_rows(data):
    first_col = [row[0] for row in data]
    empty_count = 0
    for val in first_col:
        if val is None:
            empty_count += 1
        else:
            break
    return min(empty_count + 1, 3)
```

---

## 使用示例

```python
# 加载Skill后使用
handler = ExcelMergedCellHandler('accounts.xlsx')
filled_data = handler.read_with_filled_merged('测试账号')
handler.close()
```

---

## 注意事项

1. **索引转换**: openpyxl使用1-indexed，Python列表使用0-indexed
2. **空值处理**: 填充前检查左上角值是否为None
3. **性能考虑**: 大文件可能有较多合并单元格
4. **格式保留**: `data_only=True`会丢失公式

---

## 加载要求

```yaml
1. 尝试: skill({ name: "excel-merged-cell-handler" })
2. 若失败: Read(".opencode/skills/data/excel-merged-cell-handler/SKILL.md")
```