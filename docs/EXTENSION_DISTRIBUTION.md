# 扩展分发：安装方式与上架指南（Chrome / Edge）

> 本扩展在 **Chrome 和 Edge 上是同一份代码**，Manifest V3 API 完全通用，
> `chrome-extension/` 目录一个字都不用改。下文两个浏览器都适用。
> 想了解"为什么非得用扩展拿 cookie"，见 [COOKIE_SOURCES.md](COOKIE_SOURCES.md)。

## 先回答一个问题：能不能"自动装进浏览器"？

**结论：能，但必须先上架商店。** 不上架的话，Windows 上没有任何静默安装的路子。

这不是没找到办法，是浏览器官方策略写死的。四条路对比：

| 方式 | 用户体验 | 能否自动化 | 门槛 |
|---|---|---|---|
| 开发者模式「加载已解压的扩展」 | 手动 3 步，约 30 秒 | ❌ 必须手动点 | 无 |
| 企业策略 + **自托管 CRX** | 静默 | ❌ 个人电脑上会被拦 | 需 AD 域 / 企业受管 |
| 企业策略 + **扩展已上架** | 静默、免开发者模式 | ✅ 一条 reg 命令 | 需先上架 |
| 商店手动添加 | 点一下「添加至 Chrome/Edge」 | ❌ 需手动点 | 需先上架 |

### 为什么自托管 CRX 在个人电脑上走不通

`ExtensionInstallForcelist` 的值格式是 `<扩展ID>;<update URL>`，
update URL **必须是 HTTP(S) 地址** —— 早期 Chrome 允许填本地 CRX 文件路径，
自 **Chrome 33（Windows）/ 44（macOS）起已移除**，现在只有 Linux 还支持本地 CRX。

那把 CRX 和 update XML 托管到 GitHub Pages 上、填 HTTP 地址行不行？
**在个人 Windows 上依然不行。** Chrome 官方策略文档的原文限制是：

> 在 Windows 实例上，未托管在 Chrome Web Store 的应用和扩展程序，
> **只有在该实例已加入 Active Directory 域、Azure AD，或已注册 Chrome Enterprise Core**
> 的情况下，才能被强制安装。

普通个人电脑写这条策略，`chrome://policy` 里会显示：

```
[BLOCKED] <扩展ID>;https://your-host/update.xml
系统检测到，此计算机不是由企业管理，因此该策略只能自动安装 Chrome 应用商店中的扩展程序。
```

**反过来就是好消息：一旦上架商店，这条限制就不存在了。**
此时把策略值填成商店的 update URL，普通个人电脑照样能静默强制安装。

**因此推荐路线：**

- **现在自己用**：开发者模式加载（3 步，README 里有）
- **想让别人零操作用上**：上架商店 → 然后一条注册表命令（见路线 C）
- **先上 Edge**：Edge 商店免费、审核更快，建议先上 Edge 试水

---

## 路线 A：开发者模式加载（当前方式）

**Chrome：**

1. 打开 `chrome://extensions/`
2. 右上角打开**开发者模式**
3. 点**「加载已解压的扩展程序」**，选本仓库的 `chrome-extension/` 目录

**Edge：**

1. 打开 `edge://extensions/`
2. 左下角打开**开发人员模式**
3. 点**「加载解压缩的扩展」**，选本仓库的 `chrome-extension/` 目录

同一个目录，两个浏览器都能加载，互不干扰。

装完立刻自动导出一次，之后每 30 分钟自动更新。

**已知小麻烦：** Chrome 偶尔会提示「请停用开发者模式扩展」。
这是因为未上架的扩展不受商店签名保护。遇到时去扩展页手动启用一次。
上架后就没有这个提示了。

---

## 路线 B：上架商店

两个商店**用同一个 zip 包**，不用改代码。先说结论：

| | Edge Add-ons | Chrome 网上应用店 |
|---|---|---|
| 注册费 | **免费** | $5 USD 一次性 |
| 审核时长 | 约 2 天 | 约 4 天 |
| 流量 | 小 | 大得多 |
| 建议 | **先上这个试水** | 验证过后再上 |

### 打包（两个商店通用）

```bash
cd chrome-extension
zip -r ../yt-cookie-auto.zip manifest.json background.js popup.html popup.js icons/
```

注意 zip 里**不要包含上层目录**，文件必须在 zip 根目录。

图标先生成好：

```bash
python scripts/make_icons.py     # 生成 16/32/48/128 到 chrome-extension/icons/
```

---

### B-1：Microsoft Edge Add-ons（免费，建议先做）

1. 在 [Partner Center](https://partner.microsoft.com/) 用微软账号注册
   Edge 开发者计划 —— **官方明确说明免费，无注册费**
2. 进 [Edge Add-ons 开发者仪表板](https://partner.microsoft.com/dashboard/microsoftedge/overview)
   提交新扩展，上传上面的 zip
3. 填名称、描述、截图、语言；Privacy 部分照下面"提交时的关键填写项"填
4. 提交，约 2 个工作日过审

过审后拿到扩展 ID 和商店链接。别人点一下链接就能装，不需要开发者模式。

---

### B-2：Chrome 网上应用店（$5）

1. **开发者账号**：一次性 **$5 USD** 注册费（Google 账号登录
   [Chrome 开发者控制台](https://chrome.google.com/webstore/devconsole) 后支付）
2. 上传同一个 zip
3. **扩展 ID**：首次上传后由 Google 分配，之后固定不变

两个商店的扩展 ID 是**各自独立**的（Edge 和 Chrome 会给出不同 ID），
注册表策略里要用对应商店的 ID。

### 提交时的关键填写项

审核最关注的是权限合理性，建议照下面填：

**单项用途说明（Single purpose）**

> 定时把当前 Chrome 的全部 cookie 导出为 Netscape 格式的文本文件，
> 保存到本地下载目录，供 yt-dlp 等命令行工具进行已登录身份的视频下载。

**为什么需要 `cookies` 权限**

> 这是扩展的核心功能：读取 cookie 才能导出。
> 扩展**不修改、不删除**任何 cookie，只读。

**为什么需要 `downloads` 权限**

> 用于把生成的文本文件写入用户的下载目录。
> Chrome 扩展没有通用文件系统写权限，这是唯一能把文件落盘的方式。

**为什么需要 `alarms` / `storage`**

> `alarms` 用于每 30 分钟定时触发；`storage` 仅保存上次导出时间
> 和 cookie 条数，用于弹窗展示，不保存 cookie 内容。

**数据处理声明**

- 不收集任何用户数据
- 不向任何服务器发送数据（扩展内没有任何网络请求代码）
- 不上传 cookie（导出的文件只写在本地磁盘）

这一点很重要：**本扩展的 `background.js` 里没有任何网络请求代码**，
审计时可以明确指出这一点，通常能加快审核。

### 审核时长

通常 1–3 个工作日。涉及 `cookies` 权限有时会要求补充说明，按上面填基本能过。

---

## 路线 C：上架后，用注册表静默强制安装

上架拿到扩展 ID 之后，**一条命令**就能让 Chrome 自动装好扩展：
不用开发者模式，用户不用点任何东西，而且装完标记为「由贵单位管理」，删不掉。

### 一行命令（cmd，当前用户，无需管理员）

```cmd
reg add "HKCU\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" /v 1 /d "<扩展ID>;https://clients2.google.com/service/update2/crx" /f
```

### PowerShell 等价写法

```powershell
$id = "<上架后拿到的扩展ID>"
$key = "HKCU:\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist"
New-Item -Path $key -Force | Out-Null
New-ItemProperty -Path $key -Name "1" `
  -Value "$id;https://clients2.google.com/service/update2/crx" `
  -PropertyType String -Force | Out-Null
```

仓库里也备好了脚本（带参数校验和错误处理）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_extension_policy.ps1 -ExtensionId "<扩展ID>"
```

> 在 IDE 内置终端 / 受沙箱保护的 PowerShell 里跑，可能会被拒绝写注册表
> （提示"访问被拒绝"）。换一个**普通的 PowerShell 窗口**再试即可。
> 想写 HKLM 就用管理员身份运行并加 `-Machine`。
> 卸载：`... -Uninstall`

### 生效条件

**必须完全退出 Chrome 再重开** —— 关掉窗口不算，任务管理器里确认没有
残留的 `chrome.exe` 进程。重开后在 `chrome://extensions` 就能看到扩展，
在 `chrome://policy` 能看到策略状态为「正常」（不是 `[BLOCKED]`）。

### 卸载

```cmd
reg delete "HKCU\SOFTWARE\Policies\Google\Chrome\ExtensionInstallForcelist" /v 1 /f
```

### HKCU 还是 HKLM

- `HKCU` —— 只对当前用户生效，**不需要管理员权限**，推荐
- `HKLM` —— 机器级生效，所有用户都装，但写注册表需要管理员权限

### 多人分发时的正确顺序

1. 上架拿到固定扩展 ID（上架后 ID 永久不变）
2. 把 ID 写进本仓库 `scripts/install_extension_policy.ps1` 的默认参数
3. 别人 clone 仓库后跑一条命令，扩展自动装好
4. 再跑 `python scripts/install_skill.py` 装 Skill
5. 之后他只需要把链接丢给 agent

---

## 路线 D：CI 自动上传新版本（"自动上传"的真正形态）

先说清楚边界：**首次上架必须手动** —— 要填 listing、传截图、过人工审核，
这一步没有任何 API 能代劳。

但**之后每次发新版本可以完全自动化**：打一个 `v1.0.1` 标签推上去，
GitHub Actions 自动打包 → 上传 Chrome → 上传 Edge，几分钟搞定。

仓库里已经放好了 workflow：`.github/workflows/publish-extension.yml`。

### 需要配的 Secrets

| Secret | 用途 | 从哪来 |
|---|---|---|
| `CHROME_EXTENSION_ID` | Chrome 扩展 ID | 上架后商店后台可见 |
| `CHROME_CLIENT_ID` / `CHROME_CLIENT_SECRET` / `CHROME_REFRESH_TOKEN` | Google OAuth 凭据 | Google Cloud Console 建 OAuth 客户端，scope 用 `https://www.googleapis.com/auth/chromewebstore` |
| `EDGE_PRODUCT_ID` | Edge 产品 ID | Partner Center 扩展详情页 |
| `EDGE_CLIENT_ID` / `EDGE_CLIENT_SECRET` / `EDGE_ACCESS_TOKEN_URL` | 微软 API 凭据 | Partner Center 的 API 凭据页面 |

用到的两个工具：

- Chrome：[`chrome-webstore-upload-cli`](https://www.npmjs.com/package/chrome-webstore-upload-cli)
- Edge：[`wdzeng/edge-addon`](https://github.com/wdzeng/edge-addon) GitHub Action

### 触发方式

```bash
git tag v1.0.1 && git push origin v1.0.1
```

或在 GitHub 上 Actions 页面手动 Run workflow。

> 注意版本号必须递增，两个商店都要求 `manifest.json` 里的 version 严格大于上一版。

---

## 扩展行为说明（便于你自己审查）

- `chrome.cookies.getAll({})` 取**整个 profile 的全量** cookie。
  不能用 `getAll({url})`——那样会漏掉 host-only 域（不带 www 的 `youtube.com`）
  上的 `LOGIN_INFO` / `SID` / `HSID`，导出的文件就废了。
- 只输出到 `Downloads/yt-cookies.txt`，用 `conflictAction: "overwrite"`
  覆盖同名文件，不会攒出 `(1)(2)(3)` 这种副本。
- HttpOnly 的 cookie 行加 `#HttpOnly_` 前缀——这是 Netscape 格式的约定，
  **它是数据行不是注释**，解析时不能当注释跳过。
- MV3 的 service worker 没有 DOM，不能用 `Blob` + `URL.createObjectURL`，
  所以用 `TextEncoder` + `btoa` 生成 data URL 再下载。

## 修改导出周期

改 `chrome-extension/background.js` 顶部：

```js
const INTERVAL_MINUTES = 30;
const FILENAME = "yt-cookies.txt";
```

改完在 `chrome://extensions/` 点刷新按钮重新加载即可。
