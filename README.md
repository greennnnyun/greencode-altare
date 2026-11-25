# 蛋壳栖所 · 在线租房平台（Django 本机原型）

暖白 + 蛋壳黄的租房平台原型：游客浏览筛选房源，租客完成「注册 → 收藏 → 预约 → 聊天 → 申请 → 签合同」，房东发布管理房源并处理预约。全栈 Django 单体应用，数据全部读写 MySQL 8.0。

## 技术栈

- Python 3.11+ / Django 5.x（本项目使用 Python 3.13 + Django 5.2）
- MySQL 8.0（`utf8mb4`，端口 3306，库名 `eggshell`），驱动 `mysqlclient`
- Django 模板 + HTMX 2 + Alpine.js 3（均为本地 vendor，不依赖 CDN）
- Tailwind CSS v4 + DaisyUI 5（`@tailwindcss/cli` 构建，主题与语义 token 写在 `static/src/styles.css`）
- WhiteNoise（`STATIC_ROOT`）、waitress（Windows 长期运行）

## 目录结构

```
config/        settings.py / urls.py / wsgi.py
accounts/      自定义 User、Profile、EmailOTP、认证与邮件
listings/      房源广场、详情、收藏、房东房源管理、seed 命令
bookings/      看房预约
chat/          会话与消息（4 秒轮询）
contracts/     租房申请与电子合同
templates/     全部页面模板
static/        源码样式、构建后的 app.css、HTMX/Alpine vendor
data/          全国行政区划数据 china_divisions.json（省/市/区三级，离线）
seed_media/    演示房源本地图片（seed 复制到 MEDIA_ROOT）
```

## 本机启动

### 1. 准备 Python 环境

```powershell
cd e:\danke-trae
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> 若 `mysqlclient` 编译失败，可改用 PyMySQL：`pip install PyMySQL`，并在 `config/__init__.py` 写入
> `import pymysql; pymysql.install_as_MySQLdb()`。不要改用 SQLite。

### 2. 建库与配置

```powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS eggshell CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
Copy-Item .env.example .env
```

编辑 `.env`：

```
DB_NAME=eggshell
DB_USER=root
DB_PASSWORD=<你的 MySQL 密码>
DB_HOST=127.0.0.1
DB_PORT=3306
EMAIL_HOST_USER=<QQ 邮箱>
EMAIL_HOST_PASSWORD=<QQ 邮箱 SMTP 授权码>
SECRET_KEY=<随机长字符串>
DEBUG=True
```

`.env` 已加入 `.gitignore`，请勿提交真实密码或授权码。

### 3. 前端样式构建

```powershell
npm install
npm run build:css
```

`npm run build:css` 使用 `@tailwindcss/cli` 将 `static/src/styles.css` 编译为 `static/css/app.css`。

### 4. 迁移与演示数据

```powershell
python manage.py migrate
python manage.py seed_divisions
python manage.py seed
python manage.py collectstatic --noinput
```

- `migrate` 会自动建 `Region` 表并导入区划数据；单独重导入可执行 `seed_divisions`（幂等）。
- `seed` 幂等，重复执行不会重复插入；创建 2 个演示账号与 **12 套房源，覆盖上海 / 北京 / 杭州 / 成都 4 个城市**，并把 `seed_media/` 中的本地图片复制到 `media/listings/seed/`。
- `seed` 依赖行政区划数据，若未导入会提示先执行 `seed_divisions`。

### 5. 运行

开发：

```powershell
python manage.py runserver
```

访问 http://127.0.0.1:8000/

长期运行（Windows 不支持 gunicorn）：

```powershell
waitress-serve --port=8000 config.wsgi:application
```

## 演示账号

| 身份 | 邮箱 | 密码 |
| --- | --- | --- |
| 房东 | `landlord@eggshell.cn` | `Eggshell2026` |
| 租客 | `tenant@eggshell.cn` | `Eggshell2026` |
| 后台管理员 | `admin@eggshell.cn` | `Eggshell2026` |

运营后台：http://127.0.0.1:8000/admin/，使用上方「后台管理员」账号登录，可查看与管理全部注册用户；如需新建其他管理员，可执行 `python manage.py createsuperuser`。

## 邮件服务（QQ SMTP）

- SMTP：`smtp.qq.com:465`，`EMAIL_USE_SSL=True`，`EMAIL_USE_TLS=False`
- `EMAIL_HOST_PASSWORD` 必须是邮箱设置中的 **SMTP 授权码**，不是登录密码
- 验证码邮件主题「蛋壳栖所 · 验证码」，含 6 位数字与「10 分钟内有效」
- 同一邮箱 60 秒内仅可发送 1 封；同一 IP 每小时最多 10 封
- 验证码 10 分钟过期；同一邮箱累计 5 次错误即作废

配置验证：

```powershell
python manage.py send_test_mail <收件邮箱>
```

发送失败会捕获异常并向前端返回明确提示，不会静默吞掉。

## 功能与权限要点

- 登录仅「邮箱 + 密码」；注册需邮箱验证码激活；忘记密码使用数字验证码重置，不走默认链接重置
- 密码至少 8 位且含字母与数字；连续 5 次登录失败锁定 10 分钟
- 收藏对 `(user, listing)` 唯一，重复收藏幂等
- 房东只能管理自己的房源；预约确认/取消/完成仅房源 owner 可操作
- 标记房源为「已租出」时，同一事务内把待确认预约改为已取消，并禁止新预约与新申请
- 聊天仅会话参与方可读写；只保留 `tenant_last_read_id` / `landlord_last_read_id` 两个游标字段
- 合同 `(user, listing)` 唯一；签署后锁定起租日与租期，重复提交不产生新记录
- 「租房合同」为独立一级页签，列表按待签署 / 已签署分组：租客查看本人合同，房东查看自家房源相关合同；详情仅申请人或房源 owner 可查看，签署操作仅申请人本人可执行
- 身份证照片存放在 `private_media/`，通过鉴权视图 `FileResponse` 返回，不经过 `MEDIA_URL`
- 地区为 `Region` 三级外键（省 / 市 / 区），支持全国筛选：`/?city=<市 code>&district=<区 code>`，区县下拉由 `/listings/regions/?city=<code>` 通过 HTMX 联动返回
- 房源发布表单为省 → 市 → 区三级联动，服务端校验父子归属，非法组合返回表单错误

## 验证命令

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py send_test_mail <收件邮箱>
```

## 已知限制

- **媒体仅本地演示**：`config/urls.py` 使用 `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` 提供公开图片，仅适用于本机演示；生产环境应改为对象存储 / CDN / 受控网关，且不要依赖 `DEBUG`。
- **身份证照片为本地私有存储**：`private_media/` 不对外暴露，但未做加密存储、访问审计与水印；生产需补充。
- **邮件依赖 QQ SMTP**：未配置 `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` 时注册与找回密码不可用，页面会给出明确错误提示。
- **聊天为 4 秒轮询**：页面隐藏时暂停，可见后立即拉取一次；未使用 WebSocket，适合低并发演示。
- **原型级占位**：未接入真实支付、短信、公安实名核验与地图；房源图片为本地 AI 生成演示图，非真实房源。
- **行政区划覆盖范围**：数据来自 `modood/Administrative-divisions-of-China` 的 `pca-code.json`（已落盘 `data/china_divisions.json`，运行时不联网），覆盖大陆 **31 个省级、342 个地级、3056 个区县**；**不含港澳台**（数据源未收录），直辖市按「省 = 市」归一化展示为「上海市 · 徐汇区」。如需港澳台需自行补充数据文件后重跑 `seed_divisions`。
- **seed 数据范围**：只创建 2 个演示账号与 12 套房源（4 城）；收藏、预约、会话会附带少量示例，合同请在页面中自行体验生成。
- **地区筛选参数为 code**：手改 URL 需使用区划 code（如 `?city=3101`），非法 code 会被静默忽略而不是报错。
