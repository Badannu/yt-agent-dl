# yt-agent-dl

> 把 YouTube 链接丢给你的 AI agent，它直接把视频下载好 —— 不用手动导出 cookie，不用改 yt-dlp 配置。

## 它解决什么问题

用 yt-dlp 下载 YouTube，最常见的失败是：

```
ERROR: [youtube] xxxxx: Sign in to confirm you're not a bot.
```

几乎所有人的第一反应都是"cookie 过期了，重新导一份"。**这个判断通常是错的。**

实际排查下来，真正的原因按概率排序是：

| 排名 | 真正的原因 | 怎么验证 |
|---|---|---|
| 1 | 出口 IP 信誉差（IDC / VPS 节点） | 换个家宽节点立刻好 |
| 2 | 缺 **EJS 解密组件** | 日志有 `Signature solving failed` |
| 3 | 缺 **JS 运行时**（Node） | 日志有 `No supported JavaScript runtime could be found` |
| 4 | 环境给 Node 注入了 `NODE_OPTIONS` shim | 日志有 `Access to this API has been restricted` |
| 5 | cookie 缺 `LOGIN_INFO` | cookie 文件里搜不到 LOGIN_INFO |

而且手动导 cookie 这件事本身就很烦：每次失效都要去浏览器点一遍扩展、复制、粘贴。
本项目把这一步也干掉了 —— **Chrome 扩展每 30 分钟自动导出并覆盖**，全程无感。

## 三个组件

```
┌─────────────────────────┐
│  Chrome 扩展             │  每 30 分钟自动把全量 cookie 导出成
│  yt-cookie-auto          │  Netscape 格式，覆盖写入
└───────────┬─────────────┘   Downloads/yt-cookies.txt
            │
            ▼
┌─────────────────────────┐
│  scripts/yt_dl.py        │  自动挑 cookie、自动探测 Node / ffmpeg /
│  下载主程序              │  代理端口，自动重试 5 种播放器客户端
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│  skill/SKILL.md          │  装进 AI agent，之后你只需要说
│  Agent Skill             │  "下载这个 https://youtu.be/xxx"
└─────────────────────────┘
```

## 前置条件

| 条件 | 说明 |
|---|---|
| **浏览器已登录 Google 账号** | 本项目导的是浏览器登录态。没登录的话导出的 cookie 里没有 `LOGIN_INFO`，bot 校验失败率明显上升。未登录也能下部分公开视频，但成功率低不少。**Chrome / Edge / Firefox 都行** |
| 扩展装好并导出过一次 | 装完立刻导出一次，之后每 30 分钟自动更新。**Firefox 用户可跳过这步**，直接用 `--cookies-from-browser firefox` |
| Node.js | 解 YouTube 签名必需，**没有它必定失败** |
| ffmpeg | 合并高清格式必需 |
| 代理（国内必需） | 家宽 / 住宅节点远好于 IDC 节点 |

不确定缺哪个？跑 `python yt_dl.py --diagnose` 会一次性列出来。

## 快速开始

### 1. 装依赖

```bash
pip install -U yt-dlp
```

另外需要 **Node.js**（解签名必需）和 **ffmpeg**（合并高清格式必需）。
缺哪个，`--diagnose` 会明确告诉你。

### 2. 装浏览器扩展（自动导出 cookie）

**Chrome：** `chrome://extensions/` → 右上角**开发者模式** →
**加载已解压的扩展程序** → 选 `chrome-extension/` 目录

**Edge：** `edge://extensions/` → 左下角**开发人员模式** →
**加载解压缩的扩展** → 选同一个 `chrome-extension/` 目录

同一份代码，两个浏览器通用，不用改任何文件。

装完它立刻导出一次，之后每 30 分钟自动更新。
点扩展图标能看到上次导出时间和登录状态。

> 免开发者模式 / 上架商店 / CI 自动发布：
> [docs/EXTENSION_DISTRIBUTION.md](docs/EXTENSION_DISTRIBUTION.md)
>
> 为什么非得用扩展拿 cookie？Firefox、CDP 等备选方案对比：
> [docs/COOKIE_SOURCES.md](docs/COOKIE_SOURCES.md)
>
> **用 Firefox 的话连扩展都不用装** —— `--cookies-from-browser firefox` 直接能用。

### 3. 体检

```bash
cd scripts
python yt_dl.py --diagnose
```

全绿就可以用了。有 `[WARN]` 按提示补。

### 4.（可选）装 Skill 给 AI agent

```bash
python scripts/install_skill.py
```

装完后直接对 agent 说"下载这个 https://youtu.be/xxx" 即可。

### 5. 下载

```bash
python scripts/yt_dl.py "https://youtu.be/xxxxx" \
  -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
```

## 常用参数

| 参数 | 作用 |
|---|---|
| `-f "<格式串>"` | 指定画质，如 `bestvideo[height<=1080]+bestaudio/best`。串里只写 `bestaudio` 时脚本会自动补一份带 `[ext=m4a]` 的分支优先选 AAC，避免 MP4 里塞 Opus 导致"有画面没声音" |
| `-o <目录>` | 输出目录，默认见下方「固定下载位置」 |
| `--audio` | 只要音频（m4a） |
| `--sub` | 内嵌中英字幕 |
| `--simulate` | 只解析不下载，排障时用 |
| `--diagnose` | 环境体检 |
| `--ffmpeg-dir <目录>` | ffmpeg 不在 PATH 时指定 |
| `--proxy <url>` | 手动指定代理，如 `http://127.0.0.1:7892` |
| `--node <路径>` | 手动指定 node 可执行文件 |

### 固定下载位置（不用每次敲 `-o`）

默认下载到脚本同目录的 `downloads/`。想固定到别处，写进 `scripts/config.json`：

```json
{
  "output_dir": "C:\\Users\\YourName\\Desktop\\Temp\\YouTube-Video",
  "ffmpeg_dir": "D:/tools/ffmpeg/bin"
}
```

`config.json` 不进 Git（已在 `.gitignore` 里），模板见 `config.example.json`。
优先级：**命令行 `-o` > 环境变量 `YT_OUTPUT_DIR` > `config.json` > `./downloads`**。
跑 `--diagnose` 第一行就会打印当前生效的下载目录。

## 目录结构

```
yt-agent-dl/
├── README.md
├── LICENSE
├── chrome-extension/          # Chrome 扩展：自动导出 cookie
│   ├── manifest.json
│   ├── background.js
│   ├── popup.html / popup.js
│   └── icons/                 # 上架商店用（由 scripts/make_icons.py 生成）
├── scripts/
│   ├── yt_dl.py               # 下载主程序（路径自适应）
│   ├── install_skill.py       # 把 Skill 装进 agent
│   ├── install_extension_policy.ps1  # 上架后一键静默装扩展（Windows）
│   ├── make_icons.py          # 生成扩展图标
│   └── config.example.json    # 路径兜底配置模板
├── skill/
│   └── SKILL.md               # 给 AI agent 用的完整工作流
├── docs/
│   ├── TROUBLESHOOTING.md     # 排障手册（含踩过的所有坑）
│   ├── COOKIE_SOURCES.md      # cookie 从哪来：扩展 / Firefox / CDP 对比
│   └── EXTENSION_DISTRIBUTION.md  # 扩展安装、上架商店、CI 自动发布
└── .github/workflows/
    └── publish-extension.yml  # 打 tag 自动发布到 Chrome + Edge
```

## 设计原则

1. **不做路径假设。** node / ffmpeg / yt-dlp / 代理端口 / cookie 全部运行时探测，
   拷到任何机器都能跑。探测不到的，用 `scripts/config.json` 兜底。
2. **失败时说人话。** 抓不到标准错误就把原始输出尾部打出来，
   避免出现"五个客户端全部失败"这种无法归因的空信息。
3. **别把限流当 cookie 问题。** 这是本项目最大的教训，
   具体见 [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)。

## 许可

MIT。

请遵守 YouTube 的服务条款，仅下载你有权利下载的内容。
