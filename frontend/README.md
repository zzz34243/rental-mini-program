# 前端服务

该目录保留为项目的前端侧目录。当前代码结构与后端服务目录一致，可用于小程序联调、前端服务拆分或后续迁移为真正的小程序端工程。

## 当前内容

- `app/`：服务模块代码。
- `server.py`：服务启动入口。
- `requirements.txt`：Python 依赖。
- `start_backend.ps1`：Windows 启动脚本。
- `local.env.example`：本地配置示例。

## 启动

```powershell
python -m pip install -r requirements.txt
python server.py
```

## 开源注意

不要提交真实 `local.env`、虚拟环境、缓存目录、运行日志或运行期 JSON 数据。根目录 `.gitignore` 已统一排除这些文件。
