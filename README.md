# 棚安车棚指挥中心（2026-10-21界面更新）

## 新版界面启动

建议使用 Python 3.11。安装 `requirements.txt` 后，在本目录运行：

```powershell
python -m streamlit run app.py
```

仍可使用 `shed_app.py` 作为入口。Streamlit Cloud主文件选择 `app.py`。
保留 `best.pt`、`shed_app.py`、`shed_ui.py`、`shed_auth.py`、`shed_events.py`、
`shed_runlog.py`、`assets/style.css`、`.streamlit/config.toml`、`requirements.txt`
和 `packages.txt`。Cloud仍需配置下方账户Secrets，不能匿名登录。

新版含主控制台、图片检测、视频监测、接警处置。ECharts仅展示已有数据；
今日采样数按北京时间读取运行结果，不含图片检测或尚未汇总的运行。
地点数来自已有事件，不代表摄像头在线。日志随页面重运行刷新。
短信始终为模拟，默认阈值0.1、采样1秒、连续3次确认和5次阴性恢复保持原样。
所有业务处理函数未调整。样式入口为 `assets/style.css`。

不要将运行目录、私有账户、Secrets或界面测试数据上传GitHub。

将本目录部署文件放至GitHub仓库根目录，保留上述模型、模块、样式和配置文件。旧提交包不变；新版部署包为棚安_深蓝指挥中心_20261021.zip。

## 账户与启动

安装requirements.txt后运行python -m streamlit run shed_app.py。本机默认监听127.0.0.1；服务器改监听地址后需要HTTPS和访问控制。无账户配置时拒绝访问。

账户配置支持SHED_USERS_FILE指向私有JSON文件，或Streamlit管理页面Secrets中的accounts：

```toml
[accounts.your_username]
salt = "随机盐的十六进制值"
iterations = 600000
hash = "PBKDF2-SHA256派生值"
```

使用shed_auth.make_user(password)生成三个字段。不要将明文密码或账户配置提交Git。不同人员应使用不同账号，当前所有账号权限相同，尚未实现角色分级。

## 存储与限制

SHED_DATA_DIR默认本目录/shed_runtime。Cloud本地存储不保证持久性。分析结束后可在接警台生成并下载ZIP备份，含SQLite、证据和实验文件；JSON下载仅含事件记录。恢复时停止应用，解压至新空目录并配置SHED_DATA_DIR，不覆盖旧数据。

packages.txt声明libgl1和libglib2.0-0。Linux/云环境没有实际验收。已通过的是主工程本机AppTest和底层测试，不代表线上部署成功。实时监控、真实短信、角色权限分级尚未实现。
