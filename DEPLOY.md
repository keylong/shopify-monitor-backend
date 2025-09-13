# Shopify Monitor API 部署指南

## 🚀 快速部署到 Leapcell

### 1. 准备工作

确保您已经：
- 注册了 Leapcell 账号
- 安装了 Leapcell CLI（如果需要）
- 准备好数据库（PostgreSQL 推荐）

### 2. 配置环境变量

在 Leapcell 控制台设置以下环境变量：

```bash
# 必需的环境变量
DATABASE_URL=postgresql://user:password@host:port/database
SECRET_KEY=your-secure-secret-key-here
API_KEYS=["your-api-key-1", "your-api-key-2"]

# 可选的环境变量
CORS_ORIGINS=["https://your-frontend.com"]
REDIS_URL=redis://host:port/0
```

### 3. 部署方式

#### 方式一：通过 GitHub 部署

1. 将代码推送到 GitHub 仓库
2. 在 Leapcell 控制台连接 GitHub 仓库
3. 选择分支并触发部署

#### 方式二：通过 CLI 部署

```bash
# 安装 Leapcell CLI
npm install -g @leapcell/cli

# 登录
leapcell login

# 部署
leapcell deploy
```

#### 方式三：手动部署

1. 打包代码
2. 上传到 Leapcell 控制台
3. 配置环境变量
4. 启动应用

### 4. 部署后配置

1. **数据库初始化**
   - 首次部署后，数据库表会自动创建

2. **API 密钥生成**
   - 在环境变量中设置 API_KEYS

3. **测试部署**
   ```bash
   # 使用测试脚本验证
   python test_api.py --url https://your-app.leapcell.dev
   ```

### 5. 监控和维护

- 查看日志：Leapcell 控制台 -> 日志
- 监控指标：Leapcell 控制台 -> 监控
- 扩容：调整 leap.toml 中的 scaling 配置

## 📝 重要配置说明

### leap.toml 配置

- `app_name`: 应用名称
- `instances`: 实例数量（建议生产环境至少 2 个）
- `memory`: 内存配置（MB）
- `cpu`: CPU 配置

### 数据库配置

推荐使用 PostgreSQL：
- 连接池大小：10-20
- 最大连接数：100
- 自动重连：启用

### 性能优化

1. **启用 Redis 缓存**（可选）
   ```bash
   REDIS_URL=redis://your-redis-host:6379/0
   ```

2. **调整扫描并发**
   - 修改 `DEFAULT_SCAN_INTERVAL` 避免过于频繁

3. **使用代理**（如需要）
   ```bash
   HTTP_PROXY=http://proxy:port
   ```

## 🔧 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 DATABASE_URL 格式
   - 确认网络连接
   - 验证凭据

2. **API 认证失败**
   - 检查 API_KEYS 格式（JSON 数组）
   - 确认请求头包含 X-API-Key

3. **扫描失败**
   - 检查目标网站可访问性
   - 考虑使用代理
   - 查看日志详情

## 📊 API 使用示例

### 快速扫描
```bash
curl -X POST https://your-app.leapcell.dev/api/v1/scan \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"store_url": "https://example.myshopify.com"}'
```

### 创建监控商店
```bash
curl -X POST https://your-app.leapcell.dev/api/v1/stores \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Store",
    "url": "https://example.myshopify.com",
    "scan_interval": 3600
  }'
```

## 📞 支持

如有问题，请查看：
- API 文档：`/docs`（开发环境）
- 健康检查：`/health`
- 日志文件：Leapcell 控制台