# 蛋壳栖所（Django 5 + MySQL 8）部署到 Altare 操作手册

> 适用对象：本项目（`E:\danke-trae`，Django 单体 + MySQL 8 + waitress + WhiteNoise）
> 目标平台：Altare（altr.cc，免费常驻容器：4GB 内存、24/7、任意端口、持久磁盘、Python/Docker 预置环境）
> 预计耗时：45～60 分钟。最容易卡住的是第 5.1 步（mysqlclient 编译）和第 2 步（数据库 host）。

---

## 0. 开始前必须知道的三件事

1. Altare 给的是**一台常驻容器**，不是 Django 专用 PaaS，没有"选 Python 框架一键部署"，环境要自己配。
2. 本项目强依赖 **MySQL 8**（README 明确写了"不要改用 SQLite"），所以**数据库从哪来**是本次部署的核心分叉点，必须先在第 2 步确认。
3. 免费实例无 SLA，可能随时重置/清盘。容器磁盘上的 `media/`、`private_media/` 和数据库都不是正式存储，只适合演示；上线前记得备份。

面板按钮名称可能略有差异（Server / Instance / Environment / Egg），按语义找即可。

---

## 1. 创建运行环境

1. 打开 `console.altr.cc` 注册并登录。
2. 新建一台服务器/实例，运行时优先选 **Python 3.11+ 预置环境**。
   - 不要选 Minecraft / 游戏类模板。
   - 不要选空白 Ubuntu（除非你愿意自己装 Python 和处理系统依赖）。
   - 不建议一上来选 Docker 镜像，多一层变量。
3. 建好后，把下面 4 个值抄到记事本：
   - **分配端口**（例如 `25567`）
   - **节点 IP 或分配的子域名**
   - **SFTP 地址 + 用户名 + 密码**
   - **内存/磁盘配额**（确认是 4GB 档）
4. 启动命令先不要动，等第 8 步再改。

---

## 2. 探明数据库能力（决定走哪条路线）

在面板左侧菜单找 **Databases / MySQL / 数据库**：

- **有数据库功能（路线 A，推荐）**：新建一个库，记下 4 个值：`host`、`库名`、`用户名`、`密码`。
  注意：**host 通常不是 `127.0.0.1`**，一般是节点内网 IP 或 `xxx.altr.cc`，填错就是连接超时。
- **没有数据库功能（路线 C）**：用外部免费 MySQL —— Aiven 免费层、filess.io、TiDB Cloud Serverless 任选一个，拿到 host/port/user/password，并**把容器出口 IP 加入对方白名单**（这是最常见的卡点）。
- **两条都不行（路线 B，最后考虑）**：单容器里自己装 MySQL 8。免费面板一般不给 root/apt，成功率低；若一定要走，用 Docker 镜像把 MySQL 8 和 Django 打进同一个镜像，并准备一个启动脚本先起 mysqld 再起 waitress。内存至少预留 600MB 给 MySQL。

> 以下步骤默认走 **路线 A**（面板数据库 + Python 环境）。

---

## 3. 本地打包上传文件

`.venv`（100MB）和 `node_modules`（23MB）绝对不能上传；`static/css/app.css` 已经是构建好的产物，服务器上**不需要装 Node**。

在本地 PowerShell 执行：

```powershell
$stage = "$env:TEMP\eggshell-deploy"
Remove-Item $stage -Recurse -Force -ErrorAction Ignore
robocopy E:\danke-trae $stage /E /XD .venv node_modules staticfiles .screenshots .idea __pycache__ /XF "*.pyc" "~$*.docx" ".env" > $null
Compress-Archive -Path "$stage\*" -DestinationPath "E:\danke-trae-deploy.zip" -Force
```

产出约 12MB（代码 + `data/` 0.2MB + `seed_media/` 4.7MB + `media/` 5.2MB + `static/` 0.5MB）。

`.env` 不打包（里面是真实密码和授权码），到服务器上单独创建。

---

## 4. 上传与解压

1. 用 FileZilla / WinSCP 连 SFTP（或用面板的 File Manager 直接传 zip）。
2. 上传到容器主目录（通常是 `/home/container` 或面板显示的工作目录）。
3. 解压（面板文件管理器一般有 unzip 按钮；或用 SSH 终端 `unzip -o danke-trae-deploy.zip`）。
4. 确认 `manage.py` 就在容器主目录下，否则后面所有命令都要先 `cd` 对。

---

## 5. 手动修改 4 个文件（照抄即可）

### 5.1 `requirements.txt`

把 `mysqlclient>=2.2` 这一行删掉，整份文件改为：

```
Django>=5.0,<6
PyMySQL[rsa]>=1.1
Pillow>=10
python-dotenv>=1.0
whitenoise>=6.6
waitress>=3.0
```

原因：容器里没有 `libmysqlclient` 头文件，`mysqlclient` 必然编译失败；`[rsa]` 会自动带上 `cryptography`，MySQL 8 的 `caching_sha2_password` 需要它。

### 5.2 `config/__init__.py`（现在是空文件）

写入：

```python
import pymysql
pymysql.install_as_MySQLdb()
```

### 5.3 `config/settings.py`

把第 19 行的 `ALLOWED_HOSTS = [...]` 整行替换为：

```python
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

补充：若 `migrate` 报 `Unknown system variable 'sql_mode'`，说明面板数据库是 MariaDB，把 `DATABASES` 里的 `'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"` 这一行删掉再试。

### 5.4 `config/urls.py`

把文件最后那段 `urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` 注释掉，改为无条件路由：

```python
from django.urls import re_path
from django.views.static import serve

urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
```

原因：`static()` 在 `DEBUG=False` 时会直接返回空列表，房源图片会全部 404，这是本项目最容易漏的一处。

---

## 6. 在服务器上创建 `.env`

在容器主目录建 `.env`：

```
DB_NAME=<面板库名>
DB_USER=<面板用户名>
DB_PASSWORD=<面板密码>
DB_HOST=<面板给的 host>
DB_PORT=3306
EMAIL_HOST_USER=<你的 QQ 邮箱>
EMAIL_HOST_PASSWORD=<QQ 邮箱 SMTP 授权码>
SECRET_KEY=<新生成的长随机串>
DEBUG=False
ALLOWED_HOSTS=<节点IP>,<子域名>
CSRF_TRUSTED_ORIGINS=http://<节点IP>:<端口>
```

生成 SECRET_KEY：

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

收尾：`chmod 600 .env`（避免同机其他进程读明文）。

---

## 7. 安装依赖并初始化数据

在 SSH 终端或面板 Web Console 里执行：

```bash
cd ~                       # 换到 manage.py 所在目录
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

若 `python3 -m venv` 不可用（缺 venv 模块），退而求其次：

```bash
pip install --user -r requirements.txt
```

然后初始化：

```bash
python manage.py migrate
python manage.py seed_divisions
python manage.py seed
python manage.py collectstatic --noinput
```

说明：
- `seed_divisions` 会导入 3056 个区县，约 10 秒；要放在 `seed` 之前，否则 `seed` 会提示先导区划。
- `seed` 会往 `media/listings/seed/` 复制图片，若报 Permission denied：`chmod -R u+w media private_media`。
- `collectstatic` 之后 WhiteNoise 才会在 `DEBUG=False` 下提供 CSS/JS。
- 可选：`python manage.py check --deploy` 看安全项提示。

---

## 8. 把面板启动命令改成 waitress

在面板的 **Startup Command / Start Command** 里填：

```bash
waitress-serve --listen=0.0.0.0:<面板分配的端口> --threads=4 config.wsgi:application
```

- 端口必须用面板分配的那个（例：`--listen=0.0.0.0:25567`），不能写 8000，否则面板访问不到。
- 若面板把端口放在环境变量里（`$SERVER_PORT`），也可以直接用它。
- 进程必须**前台**运行：不要 `nohup`、不要结尾加 `&`、不要再套一层 `runserver`，否则面板会判定进程退出并反复重启。
- 保存后点重启，控制台应出现 `Serving on http://0.0.0.0:25567`。

---

## 9. 验收清单（逐条打勾）

1. 浏览器打开 `http://<节点IP>:<端口>`，首页出现 12 套演示房源。
2. 房源缩略图能正常显示（验证第 5.4 步生效）。
3. 打开 `/admin/`，用 `admin@eggshell.cn` / `Eggshell2026` 登录。
4. 提交一次登录或注册表单，不出现 403（验证 CSRF 配置）。
5. 注册新账号能收到 6 位验证码邮件（验证 SMTP 出站）；收不到先按第 10 条处理。
6. 收藏、预约、聊天各操作一次，刷新后状态还在。
7. 面板重启容器后，数据和上传的图片仍在（验证持久磁盘）。
8. 手机 4G 访问一次，确认不是只对本机可达。

---

## 10. 报错对照表

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `400 Bad Request (DisallowedHost)` | `ALLOWED_HOSTS` 没加节点 IP/子域名 | 补 `.env` 里的 `ALLOWED_HOSTS`，重启 |
| `403 CSRF verification failed` | `CSRF_TRUSTED_ORIGINS` 为空或漏协议头 | 写全 `http://IP:端口`，https 则写 `https://域名` |
| 页面打不开、连接超时 | 启动命令端口 ≠ 面板端口，或没绑 `0.0.0.0` | 两者对齐，`--listen=0.0.0.0:<端口>` |
| 控制台反复重启/闪退 | 依赖没装全、前台进程退出 | 看控制台首屏报错，先手动跑命令确认能起 |
| 图片全部 404 | 第 5.4 步没做（`DEBUG=False` 下 `static()` 失效） | 换成 `re_path + serve` |
| `ModuleNotFoundError: No module named 'MySQLdb'` | 没装 PyMySQL 或没写 `config/__init__.py` | 回到 5.1 / 5.2，确认 venv 已激活 |
| `OperationalError (2002)` 连不上库 | `DB_HOST` 写成 `127.0.0.1`；或库只允许内网 | 用面板给的 host；外部库要加白名单 |
| `RuntimeError: cryptography is required` | PyMySQL 连 MySQL 8 | 用 `PyMySQL[rsa]`，或单独 `pip install cryptography` |
| `Unknown system variable 'sql_mode'` | 面板数据库是 MariaDB | 删掉 `init_command` |
| 验证码邮件 timed out | 465 出站被主机阻断 | 改 `EMAIL_PORT=587` + `EMAIL_USE_TLS=True`；或先临时换 console backend 验证页面流程 |
| 容器被杀 / MemoryError | 内存吃满（常见于容器内又跑了 MySQL） | 降 `--threads`；数据库放面板侧或外部 |
| CSS/JS 不生效 | 没跑 `collectstatic` 或 `DEBUG=False` 下没走 WhiteNoise | 重跑 `collectstatic --noinput`，确认中间件顺序 |

---

## 11. 可选增强

- **自定义域名 + HTTPS**：面板支持绑定域名，套 Cloudflare 免费代理即可拿到 https；记得同步改 `.env` 的 `ALLOWED_HOSTS` 和 `CSRF_TRUSTED_ORIGINS`（加 `https://你的域名`）。
- **媒体外置**：现在是 5MB 本地图片，短期不用动；后期换对象存储，`MEDIA_ROOT` 改走 S3 兼容接口即可。
- **备份**：免费实例没有备份功能，演示前执行 `mysqldump` 导出 + 打包 `media/`、`private_media/` 存本地。

---

## 12. 一句话回顾

建 Python 环境 → 拿 MySQL 连接信息 → 传代码（不含 .venv/node_modules）→ 改 4 个文件（依赖、`__init__.py`、settings、urls）→ 写 `.env` → migrate/seed/collectstatic → 启动命令换 waitress 监听面板端口 → 按验收清单过一遍。
