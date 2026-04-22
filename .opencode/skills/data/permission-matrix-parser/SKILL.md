---
name: permission-matrix-parser
description: "权限矩阵Excel解析：角色账号表头解析、多值单元格拆分、权限符号解析、生成accounts.json和workflow_config.json"
dependencies:
  - excel-merged-cell-handler
---

# Permission Matrix Parser Skill

> 专用于权限矩阵Excel解析 - 账号表 + 权限矩阵表

---

## 输入格式

INFO.xlsx典型结构：

**Sheet 1: 测试账号表**
```
分类 | 角色名 | 公共服务角色名 | 权限说明 | 账号 | 密码
软件NRE | 生态经理 | 软件NRE生态经理 | 1.软件NRE的审核... | test1020 | Pr0d1234
```

**Sheet 2: 权限矩阵表**
```
一级菜单/流程节点 | 二级菜单/功能 | 生态经理test1020 | 技术评估专家组组长test1021 | ...
软件NRE | 提交终止 | √ | × | ...
NRE申请预审 | 同意/驳回 | √ | × | ...
```

---

## 核心功能

| 功能 | 函数 |
|------|------|
| 角色账号表头解析 | `parseRoleAccountHeader()` |
| 多账号单元格拆分 | `parseMultiValueCell()` |
| 权限符号解析 | `parsePermissionSymbol()` |
| Sheet类型检测 | `is_account_sheet()`, `is_permission_matrix_sheet()` |
| 合并单元格处理 | 调用 `excel-merged-cell-handler` |

---

## Python实现

### parseRoleAccountHeader 函数

```python
import re

def parseRoleAccountHeader(header):
    """
    解析表头: "生态经理test1020" → { role_name: "生态经理", account_ids: ["test1020"] }
    """
    accounts = re.findall(r'test[0-9]+', str(header))
    role_name = re.sub(r'test[0-9]+', '', str(header)).strip()
    role_name = re.sub(r'\s+', '', role_name)
    return {
        'raw_header': str(header),
        'role_name': role_name,
        'account_ids': accounts
    }
```

### parseMultiValueCell 函数

```python
def parseMultiValueCell(value):
    """
    解析多值单元格: "test1024 test1033" → ["test1024", "test1033"]
    """
    if not value:
        return []
    import re
    return re.findall(r'test[0-9]+', str(value))
```

### parsePermissionSymbol 函数

```python
def parsePermissionSymbol(value):
    """
    解析权限符号: √ → True, × → False, 空白 → None
    """
    if value == '√' or value == '✓' or value == 'Y' or value == '是':
        return True
    if value == '×' or value == '✗' or value == 'N' or value == '否':
        return False
    return None
```

### Sheet类型检测

```python
def is_account_sheet(sheet):
    headers = [cell.value for cell in sheet[1]]
    keywords = ["账号", "密码", "用户名", "account", "password"]
    return any(kw in str(h) for h in headers for kw in keywords)

def is_permission_matrix_sheet(sheet):
    for row in sheet.iter_rows(min_row=1, max_row=5):
        for cell in row:
            if cell.value in ["√", "×", "✓", "✗"]:
                return True
    return False
```

### parse_account_sheet 函数

```python
def parse_account_sheet(ws):
    """
    解析账号Sheet，返回账号列表和角色-账号映射
    """
    from openpyxl import load_workbook
    import re
    
    # 使用excel-merged-cell-handler填充合并单元格
    raw_data = []
    for row in ws.iter_rows(values_only=True):
        raw_data.append(list(row))
    
    # 填充合并单元格
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        r_start = min_row - 1
        r_end = max_row
        c_start = min_col - 1
        c_end = max_col
        value = raw_data[r_start][c_start]
        if value is not None:
            for r in range(r_start, r_end):
                for c in range(c_start, c_end):
                    raw_data[r][c] = value
    
    headers = raw_data[0]
    accounts = []
    role_account_map = {}
    
    current_role = None
    current_role_display = None
    current_permission_desc = None
    current_category = None
    
    for row_data in raw_data[1:]:
        category = row_data[0]
        role_name = row_data[1]
        public_role_name = row_data[2]
        permission_desc = row_data[3]
        account_str = str(row_data[4] or '')
        password = row_data[5]
        
        if category:
            current_category = category
        if role_name:
            current_role = role_name
            current_role_display = public_role_name or role_name
            current_permission_desc = permission_desc
        
        account_ids = re.findall(r'test[0-9]+', account_str)
        
        for account_id in account_ids:
            pwd = str(password) if password else 'NOT_PROVIDED'
            accounts.append({
                'id': account_id,
                'role': current_role,
                'role_display': current_role_display,
                'category': current_category,
                'permission_description': current_permission_desc,
                'credentials': {'username': account_id, 'password': pwd}
            })
            if current_role not in role_account_map:
                role_account_map[current_role] = []
            role_account_map[current_role].append(account_id)
    
    return accounts, role_account_map
```

### parse_permission_matrix_sheet 函数

```python
def parse_permission_matrix_sheet(ws):
    """
    解析权限矩阵Sheet，返回权限矩阵和流程节点
    """
    import re
    
    # 填充合并单元格
    raw_data = []
    for row in ws.iter_rows(values_only=True):
        raw_data.append(list(row))
    
    for merged_range in ws.merged_cells.ranges:
        min_col, min_row, max_col, max_row = merged_range.bounds
        r_start = min_row - 1
        r_end = max_row
        c_start = min_col - 1
        c_end = max_col
        value = raw_data[r_start][c_start]
        if value is not None:
            for r in range(r_start, r_end):
                for c in range(c_start, c_end):
                    raw_data[r][c] = value
    
    # 解析表头
    header_row = raw_data[0]
    role_headers = []
    for col_idx, h in enumerate(header_row[3:], 3):
        if h:
            role_headers.append({
                'col_index': col_idx,
                **parseRoleAccountHeader(h)
            })
    
    # 解析权限数据
    permission_matrix = {}
    workflow_nodes = []
    
    for row_idx, row in enumerate(raw_data[2:], 3):
        level1_menu = row[0] if len(row) > 0 else None
        level2_menu = row[1] if len(row) > 1 else None
        function_name = row[2] if len(row) > 2 else None
        
        if not function_name:
            continue
        
        permissions = {}
        for rh in role_headers:
            col_idx = rh['col_index']
            perm_value = row[col_idx] if len(row) > col_idx else None
            permissions[rh['role_name']] = parsePermissionSymbol(perm_value)
        
        full_path = f"{level1_menu or ''}/{level2_menu or ''}/{function_name}".strip('/')
        matrix_key = full_path if full_path != function_name else function_name
        
        permission_matrix[matrix_key] = permissions
        
        required_roles = [r for r, p in permissions.items() if p is True]
        
        workflow_nodes.append({
            'node_id': f'node_{row_idx-2}',
            'node_name': function_name,
            'level1_menu': level1_menu,
            'level2_menu': level2_menu,
            'full_path': full_path,
            'required_roles': required_roles,
            'permissions': permissions
        })
    
    return permission_matrix, workflow_nodes, role_headers
```

### parse_permission_excel 主函数

```python
def parse_permission_excel(file_path):
    """
    解析权限Excel文件，返回完整结果
    """
    from openpyxl import load_workbook
    
    wb = load_workbook(file_path, data_only=True)
    
    results = {
        'accounts': [],
        'role_account_map': {},
        'permission_matrix': {},
        'workflow_nodes': [],
        'role_headers': []
    }
    
    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        
        if is_account_sheet(sheet):
            accounts, role_account_map = parse_account_sheet(sheet)
            results['accounts'] = accounts
            results['role_account_map'] = role_account_map
        
        elif is_permission_matrix_sheet(sheet):
            matrix, nodes, headers = parse_permission_matrix_sheet(sheet)
            results['permission_matrix'] = matrix
            results['workflow_nodes'] = nodes
            results['role_headers'] = headers
    
    wb.close()
    return results
```

---

## 输出文件

| 文件 | 内容 |
|------|------|
| `accounts.json` | 账号列表、role_account_map |
| `permission_matrix.json` | 功能×角色权限矩阵 |
| `workflow_config.json` | 流程节点、required_roles |

---

## 输出格式

### accounts.json

```json
{
  "schema": "accounts_schema",
  "accounts": [
    {
      "id": "test1020",
      "role": "生态经理",
      "role_display": "软件NRE生态经理",
      "category": "软件NRE",
      "credentials": { "username": "test1020", "password": "Pr0d1234" }
    }
  ],
  "role_account_map": {
    "生态经理": ["test1020"]
  }
}
```

### permission_matrix.json

```json
{
  "schema": "permission_matrix_schema",
  "matrix": {
    "软件NRE//提交终止": {
      "生态经理": true,
      "技术评估专家组组长": false
    }
  },
  "role_headers": [
    { "role_name": "生态经理", "account_ids": ["test1020"] }
  ]
}
```

### workflow_config.json

```json
{
  "workflows": [
    {
      "workflow_id": "software_nre",
      "nodes": [
        {
          "node_id": "node_1",
          "node_name": "提交终止",
          "required_roles": ["生态经理"]
        }
      ]
    }
  ]
}
```

---

## 加载要求

```yaml
# 必须先加载excel-merged-cell-handler
1. skill({ name: "excel-merged-cell-handler" })
2. skill({ name: "permission-matrix-parser" })
# 若失败则读取文件
```