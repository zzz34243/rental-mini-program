# Contributing

欢迎对本项目进行改进。提交贡献前建议先阅读根目录 `README.md`，了解项目结构、启动方式和核心模块职责。

## Development Setup

```powershell
python -m pip install -r requirements.txt
python server.py
```

如需配置本地环境变量：

```powershell
Copy-Item local.env.example local.env
```

请不要提交真实 `local.env`、虚拟环境、运行日志或运行期 JSON 数据。

## Suggested Workflow

1. 创建新分支。
2. 修改代码或文档。
3. 本地运行服务并验证接口。
4. 提交 Pull Request，并说明修改内容和验证方式。

## Code Style

- 保持模块边界清晰。
- 新增数据源时优先实现采集器并注册到 `CollectorRegistry`。
- 新增推荐逻辑时保留可解释字段，便于前端展示和调试。
- 避免将密钥、个人配置和采集到的运行数据提交到仓库。
