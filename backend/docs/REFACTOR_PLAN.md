# 后端代码结构重构计划（渐进式）

## 一、现状分析

### 基本统计
- **总文件数**: 68个
- **总代码行数**: 15,375行
- **顶层文件**: 25个（6,732行）- 最混乱的部分

### 兼容层识别（关键！）
| 文件 | 行数 | 说明 |
|------|------|------|
| `amap.py` | 62 | **确认是兼容层**，从services.map重新导出所有函数 |
| `services/map/__init__.py` | 43 | 包初始化，重新导出 |
| `services/rag/__init__.py` | 23 | 包初始化，重新导出 |

**重要**: `amap.py` 只是兼容层，真正的实现在 `services/map/client.py`（239行）。迁移时必须先迁移真正的实现，再处理兼容层。

### 核心大文件
| 文件 | 行数 | 职责 |
|------|------|------|
| `planner.py` | 721 | 行程规划引擎主入口 |
| `intent.py` | 646 | 意图识别与参数提取 |
| `admin_store.py` | 659 | 后台管理数据存储 |
| `admin_router.py` | 515 | 后台管理接口 |
| `ai.py` | 454 | AI大模型封装 |

---

## 二、目标目录结构

```
app/
├── main.py                    # 入口类（保持不变）
├── config.py                  # 配置类（保持不变）
├── app_context.py             # 统一调度类（新增）
│
├── api/                       # 接口类
│   ├── auth.py, plan.py, explore.py, trips.py, ...
│   └── admin/                 # 后台管理接口
│
├── core/                      # 核心能力类
│   ├── planner_engine.py      # 原 planner.py
│   ├── planner/               # 规划辅助模块
│   ├── orchestrator/          # 编排器
│   └── session/               # 会话管理
│
├── ai/                        # AI能力类
│   ├── llm.py                 # 原 ai.py
│   ├── intent.py
│   └── rag/                   # RAG检索增强
│
├── map/                       # 地图服务类
│   ├── client.py              # 原 services/map/client.py（真正的实现）
│   ├── geocode.py, poi.py, route.py, weather.py
│   └── geo_local.py
│
├── data/                      # 数据访问层
│   ├── database.py, models.py
│   ├── userstore.py, admin_store.py, dict_store.py
│   └── repositories/          # 数据库查询类（新增）
│
├── security/                  # 安全类
│   ├── auth.py, db_security.py, login_security.py
│   ├── rate_limiter.py, security_middleware.py
│
├── infrastructure/            # 基础设施类
│   ├── cache.py, logger.py, metrics.py
│   ├── exceptions.py, circuit_breaker.py, redis_client.py
│
└── utils/                     # 工具类
    └── responses.py
```

---

## 三、分阶段迁移计划

### 阶段零：准备工作 ✅
- [x] 提交当前代码，创建稳定回滚点（e07b4c6）
- [x] 详细梳理每个文件的职责和依赖关系
- [x] 识别所有兼容层和真正的实现文件
- [x] 制定详细的迁移计划

### 阶段一：创建统一调度类 AppContext（不改变目录结构）
**目标**: 创建 `AppContext` 统一调度类，逐步将核心服务接入。

**步骤**:
1. 创建 `app/app_context.py`，实现服务定位器模式
2. 注册所有核心服务的工厂函数（懒加载）
3. 在 `main.py` 中初始化 `AppContext`
4. 逐步将关键接口中的直接导入改为通过 `AppContext` 访问
5. 测试确保所有功能正常

**风险**: 低，不改变目录结构

---

### 阶段二：迁移基础设施层（infrastructure）
**迁移文件**: cache.py, logger.py, metrics.py, exceptions.py, circuit_breaker.py, redis_client.py

**原则**: 逐个迁移，每次1个，迁移后立即测试，提交代码。

---

### 阶段三：迁移安全层（security）
**迁移文件**: security_middleware.py, rate_limiter.py, login_security.py, db_security.py

---

### 阶段四：迁移工具类和数据访问层
**迁移文件**: responses.py, database.py, models.py, userstore.py, admin_store.py, dict_store.py

---

### 阶段五：迁移地图服务层（map）⚠️ 高风险
**关键**: 
- `amap.py` 是兼容层（62行），**不要先迁移它**
- 真正的实现在 `services/map/client.py`（239行）
- 先迁移 `services/map/` 下的真正实现，再处理 `amap.py` 兼容层

**迁移顺序**:
1. 迁移 `services/map/client.py` → `map/client.py`
2. 迁移 `services/map/geocode.py` → `map/geocode.py`
3. 迁移 `services/map/poi.py` → `map/poi.py`
4. 迁移 `services/map/route.py` → `map/route.py`
5. 迁移 `services/map/weather.py` → `map/weather.py`
6. 迁移 `geo_local.py` → `map/geo_local.py`
7. 最后：将 `amap.py` 改为指向 `map/` 的兼容层，逐步替换引用后删除

---

### 阶段六：迁移AI能力层（ai）
**迁移文件**: ai.py→ai/llm.py, intent.py, services/rag/*

---

### 阶段七：迁移核心能力层（core）⚠️ 最复杂
**迁移文件**: planner.py→core/planner_engine.py, services/planner/*, services/orchestrator/*, services/session/*

**迁移顺序**:
1. 先迁移 `services/planner/` 下的8个辅助文件
2. 再迁移主文件 `planner.py` → `core/planner_engine.py`
3. 迁移 `services/orchestrator/`
4. 迁移 `services/session/`

---

### 阶段八：迁移接口层（api）
**迁移文件**: routers/*→api/*, admin_router.py→api/admin/, health.py

**最后迁移**，因为接口层依赖所有其他层。

---

### 阶段九：清理和优化
1. 删除 `amap.py` 兼容层（确认所有引用都已更新）
2. 删除空的 `services/` 和 `routers/` 目录
3. 优化 `AppContext`，减少直接导入
4. 完善文档和注释
5. 运行完整测试

---

## 四、迁移原则

1. **每次只迁移一个文件或一个模块**，迁移后立即测试
2. **先迁移被依赖少的底层模块**，再迁移上层模块
3. **保留兼容层直到所有引用都更新完毕**，不要急于删除
4. **每个阶段完成后提交代码**，创建回滚点
5. **使用 `AppContext` 减少直接导入依赖**，逐步收束调用入口
6. **测试驱动**，每个文件迁移后必须验证功能正常

---

## 五、风险控制

### 回滚策略
- 每个阶段完成后提交代码，创建回滚点
- 如果某个文件迁移失败，可以单独回滚该文件
- 如果整个阶段失败，可以回滚到阶段开始前的提交

### 兼容层策略
- `amap.py` 等兼容层在迁移过程中保留，指向新位置
- 所有引用更新完毕后，再删除兼容层
- 避免一次性删除导致大量引用错误

---

## 六、时间估算

| 阶段 | 内容 | 预计时间 |
|------|------|----------|
| 阶段零 | 准备工作 | ✅ 已完成 |
| 阶段一 | AppContext | 0.5天 |
| 阶段二 | 基础设施层 | 0.5天 |
| 阶段三 | 安全层 | 0.5天 |
| 阶段四 | 工具类和数据访问层 | 1天 |
| 阶段五 | 地图服务层 | 1天 |
| 阶段六 | AI能力层 | 1天 |
| 阶段七 | 核心能力层 | 1.5天 |
| 阶段八 | 接口层 | 0.5天 |
| 阶段九 | 清理和优化 | 0.5天 |
| **总计** | | **约7天** |

---

## 七、当前进度

- [x] 阶段零：准备工作（已完成）
- [ ] 阶段一：创建统一调度类 AppContext
- [ ] 阶段二：迁移基础设施层
- [ ] 阶段三：迁移安全层
- [ ] 阶段四：迁移工具类和数据访问层
- [ ] 阶段五：迁移地图服务层
- [ ] 阶段六：迁移AI能力层
- [ ] 阶段七：迁移核心能力层
- [ ] 阶段八：迁移接口层
- [ ] 阶段九：清理和优化
