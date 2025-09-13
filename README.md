# Shopify Monitor Backend API

企业级Shopify库存监控系统后端服务，基于FastAPI构建，使用cloudscraper绕过Cloudflare保护，提供强健稳定的库存追踪能力。

## ✨ 特性

- 🚀 **高性能异步API** - 基于FastAPI和异步Python
- 🛡️ **Cloudflare绕过** - 使用cloudscraper自动处理反爬虫机制
- 📊 **实时库存监控** - 自动扫描和追踪库存变化
- 📈 **历史数据分析** - 库存趋势和销售分析
- 🔔 **智能警报系统** - 低库存和缺货自动提醒
- 🌐 **Webhook支持** - 实时推送库存变化
- 🔒 **API密钥认证** - 安全的访问控制
- 📦 **数据导出** - 支持CSV和JSON格式

## 🛠️ 技术栈

- **框架**: FastAPI
- **抓取**: cloudscraper, httpx, BeautifulSoup4
- **数据库**: SQLAlchemy (支持PostgreSQL/SQLite)
- **调度**: APScheduler
- **验证**: Pydantic
- **日志**: Loguru

## 📦 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/shopify-monitor-backend.git
cd shopify-monitor-backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 复制环境变量配置
cp .env.example .env
# 编辑.env文件，设置你的配置
```

## 🚀 快速开始

### 本地运行

```bash
# 开发模式
python -m uvicorn app.main:app --reload

# 或使用启动脚本
chmod +x run.sh
./run.sh
```

API将在 http://localhost:8000 启动

### API文档

访问 http://localhost:8000/docs 查看交互式API文档

### 快速测试

```bash
# 运行快速测试
python quick_test.py

# 运行完整测试套件
python test_api.py
```

## 📚 API端点

### 核心功能

- `POST /api/v1/scan` - 快速扫描任意Shopify商店
- `GET /health` - 健康检查

### 商店管理

- `GET /api/v1/stores` - 获取商店列表
- `POST /api/v1/stores` - 创建新商店
- `GET /api/v1/stores/{id}` - 获取商店详情
- `PATCH /api/v1/stores/{id}` - 更新商店
- `DELETE /api/v1/stores/{id}` - 删除商店
- `POST /api/v1/stores/{id}/scan` - 触发扫描

### 监控功能

- `GET /api/v1/monitor/inventory/{store_id}` - 获取当前库存
- `GET /api/v1/monitor/inventory-history/{store_id}` - 库存历史
- `GET /api/v1/monitor/stock-changes/{store_id}` - 库存变化
- `GET /api/v1/monitor/alerts` - 库存警报
- `GET /api/v1/monitor/low-stock-items` - 低库存商品

### 分析报表

- `GET /api/v1/analytics/overview` - 总览统计
- `GET /api/v1/analytics/store/{id}/analytics` - 商店分析
- `GET /api/v1/analytics/export/inventory` - 导出库存
- `GET /api/v1/analytics/reports/daily-summary` - 日报

### Webhook管理

- `GET /api/v1/webhooks` - Webhook列表
- `POST /api/v1/webhooks` - 创建Webhook
- `PATCH /api/v1/webhooks/{id}` - 更新Webhook
- `DELETE /api/v1/webhooks/{id}` - 删除Webhook
- `POST /api/v1/webhooks/{id}/test` - 测试Webhook

## 🔐 认证

所有API端点（除了health）都需要API密钥认证：

```bash
curl -H "X-API-Key: your-api-key" http://localhost:8000/api/v1/stores
```

## 📝 使用示例

### 快速扫描商店

```python
import httpx

async def scan_store():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/scan",
            headers={"X-API-Key": "your-api-key"},
            json={"store_url": "https://example.myshopify.com"}
        )
        return response.json()
```

### 创建监控商店

```python
async def create_store():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/stores",
            headers={"X-API-Key": "your-api-key"},
            json={
                "name": "Example Store",
                "url": "https://example.myshopify.com",
                "scan_interval": 3600,
                "notify_low_stock": True,
                "low_stock_threshold": 10
            }
        )
        return response.json()
```

## 🚢 部署

### Leapcell部署

项目已配置好Leapcell部署：

1. 推送代码到GitHub
2. 在Leapcell控制台连接GitHub仓库
3. 配置环境变量
4. 自动部署

详细部署说明请参考 [DEPLOY.md](DEPLOY.md)

### 环境变量

必需的环境变量：

- `DATABASE_URL` - 数据库连接URL
- `SECRET_KEY` - 应用密钥
- `API_KEYS` - API密钥列表（JSON数组）

可选的环境变量：

- `REDIS_URL` - Redis缓存URL
- `HTTP_PROXY` - HTTP代理
- `CORS_ORIGINS` - CORS允许的源

## 📊 监控指标

系统提供以下监控指标：

- 扫描成功率
- 平均扫描时间
- 库存变化趋势
- 低库存警报
- API响应时间

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可

MIT License

## 📧 联系

如有问题或建议，请提交Issue或联系维护者。

---

**注意**: 请确保遵守Shopify的服务条款和robots.txt规则。本工具仅用于合法的库存监控目的。