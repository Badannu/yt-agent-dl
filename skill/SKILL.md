---
name: yt-agent-dl
description: 当用户发来 YouTube（youtu.be / youtube.com）链接并要求下载视频、下载音频、保存到本地，或抱怨 yt-dlp / ytDownloader 报 "Sign in to confirm you're not a bot"、下载失败、画质不对时使用。自动完成 cookie 装载、签名解密、代理探测与格式合并。
---

# yt-agent-dl：把 YouTube 链接变成下载好的文件

## 你的目标

用户丢给你一个 YouTube 链接，你把视频下载下来并告诉他在哪。
**不要**让用户去手动导出 cookie、不要让他去改 yt-dlp 配置。

## 前置条件（首次使用时确认一次）

| # | 条件 | 缺失后果 | 怎么确认 |
|---|---|---|---|
| 1 | **浏览器已登录 Google 账号** | cookie 里没有 `LOGIN_INFO`，bot 校验失败率明显上升 | 打开 youtube.com，右上角有头像。Chrome / Edge / Firefox 都行 |
| 2 | 扩展已装并导出过一次 | 找不到 cookie 文件 | `~/Downloads/yt-cookies.txt` 存在 |
| 3 | Node.js | 解不开签名，**必定失败** | `node -v` |
| 4 | ffmpeg | 高清格式无法合并成 mp4 | `ffmpeg -version` |
| 5 | 代理可用（国内） | 连不上 YouTube | 体检会明确提示 |

**第 1 条最容易漏。** 具体说明：

- 本项目导的是**浏览器里的登录态**。浏览器没登录 Google，导出来的就是一堆匿名
  会话 cookie，没有 `LOGIN_INFO`，体检会报 `[WARN] cookie ... LOGIN_INFO=无`。
- 浏览器不限：Chrome / Edge 用同一个扩展；**Firefox 连扩展都不用装**，
  直接 `python -m yt_dlp --cookies-from-browser firefox "<链接>"` 就行
  （Firefox 的 cookie 库没有 Chrome 127+ 那层 App-Bound Encryption）。
- **没登录不等于完全下不了。** 公开视频有时照样能过，所以别看到"未登录"就放弃——
  先 `--simulate` 试一次，能过就继续下载。
- 但如果持续报 bot 校验，**让用户去登录 Google 账号是性价比最高的一步**。
  登录后等扩展下次自动导出（≤30 分钟），或在扩展弹窗里手动触发立即导出。
- 用户不想用主力 profile 登录的话，可以新建一个**专用浏览器 profile**
  登录一个账号专供下载，扩展装在这个 profile 里即可 —— cookie 按 profile 隔离。

> 别在 Chrome/Edge 上试 `--cookies-from-browser chrome`：Chrome 127+ 的
> App-Bound Encryption 已经把这条路堵死了，会报
> `Could not copy Chrome cookie database`。这个报错有误导性——
> 听起来像文件被占用，实际是密钥拿不到，复制出来也解不开。

## 核心认知（先看这个，能省掉 90% 的误判）

YouTube 报 `Sign in to confirm you're not a bot` 时，**绝大多数情况跟 cookie 无关**。
真正的原因按概率排序：

| 排名 | 原因 | 症状特征 |
|---|---|---|
| 1 | **出口 IP 信誉差**（IDC/VPS 节点） | 换节点立刻好；热门视频能下、冷门不能 |
| 2 | **缺 EJS 解密组件** | 日志有 `Signature solving failed` / `n challenge solving failed` |
| 3 | **缺 JS 运行时** | 日志有 `No supported JavaScript runtime could be found` |
| 4 | **NODE_OPTIONS 注入了 shim** | 日志有 `Access to this API has been restricted. Use --allow-fs-read` |
| 5 | cookie 缺 `LOGIN_INFO` | cookie 文件里搜不到 LOGIN_INFO |

**所以：不要一上来就折腾 cookie。** 先跑体检，看是哪一条。

## 工作流

### 第 1 步：环境体检（首次使用 / 下载失败时必做）

```bash
cd "{{REPO_PATH}}/scripts"
python yt_dl.py --diagnose
```

看输出里有没有 `[WARN]` / `[FAIL]`：

- `[FAIL] yt-dlp` → **通常是"用错了 python"，不是没装。** yt-dlp 装在某个 venv 里，
  而你随手用了另一个 python 跑脚本。脚本会自动扫一遍并打印**哪个 python 装了**，
  用那个跑就行。**别急着 pip install 重装。**（真没装它才会让你装）
- `[WARN] Node` → 装 Node.js。没有它解不开签名，必定失败
- `[WARN] ffmpeg` → 装 ffmpeg，或 `--ffmpeg-dir <目录>` 指定，
  或写进 `scripts/config.json` 的 `ffmpeg_dir`
- `[WARN] cookie ... LOGIN_INFO=无` → 在 Chrome 登录 Google，让扩展重新导出
- `[WARN] 代理` → 开代理软件（国内必需）；顺带提醒：**家宽/住宅节点远好于 IDC 节点**

### 第 2 步：下载

```bash
cd "{{REPO_PATH}}/scripts"
python yt_dl.py "<用户给的链接>" -f "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
```

常用参数：

- `-f "..."` 画质。用户说 1080p 就用上面那条；没指定就用默认（`bestvideo+bestaudio/best`）
- **用户指定语言时（"下英文的"）必须显式锁音轨语言**：
  `-f "bestvideo[height<=1080]+bestaudio[language^=en]/best[height<=1080]/best"`
  YouTube 现在普遍带多条配音轨（auto-dub），日志里音轨会显示成 `f140-6` 这种带序号的
  形式——**说明它在多条音轨里挑**，默认选中未必是你要的语言。与 `[ext=m4a]` 自动改写
  兼容（`bestaudio[ext=m4a][language^=en]` 是合法串联）。
- `-o <目录>` 输出目录，默认 `./downloads`。**用户指定了固定下载目录的话，写进
  `scripts/config.json` 的 `output_dir`**（或设环境变量 `YT_OUTPUT_DIR`），
  以后就不用每次敲 `-o` 了。优先级：`-o` > `YT_OUTPUT_DIR` > `config.json` > `./downloads`
- `--audio` 只要音频（m4a）
- `--sub` 内嵌中英字幕
- `--simulate` 只解析不下载，**排障时先用它**，省时间且不加剧限流

脚本会依次尝试 5 种播放器客户端（默认 → tv → web_embedded → mweb → web_safari），
间隔递增 5/10/15/20 秒。

### 第 3 步：交付前必须核验

**别只看日志里的格式 ID 就报分辨率。** itag 和实际分辨率不是固定一对一
（同一个 itag 398 在不同视频上可能是 720p）。下载完用 ffprobe 验一次：

```bash
ffprobe -v error \
  -show_entries stream=codec_type,codec_name,channels,width,height:stream_tags=language \
  -show_entries format=duration,size \
  -of default=noprint_wrappers=1 "<文件>"
```

用户点名要某种语言时，看输出里的 `TAG:language=`（如 `eng`）。
不对照这步，就可能交付一个"画质对了但语言错了"的文件。

**顺手看一眼音轨编码**——输出里应该同时有 `codec_type=video` 和
`codec_type=audio`。如果音轨是 **`opus`**，Windows 自带播放器、QuickTime、
部分剪辑软件会**有画面没声音**（MP4 容器里的 Opus 兼容性很差）。
脚本已默认优先选 AAC(`itag 140`) 规避这个问题；万一还是 opus，交付前转一下：

```bash
ffmpeg -i in.mp4 -c:v copy -c:a aac -b:a 192k -movflags +faststart out.mp4
```

视频流不重编码，几秒完成。

如果实际分辨率低于用户要求，**先查片源最高有多少**：

```bash
python -m yt_dlp -F "<链接>"     # 看完整格式列表
```

片源本身没有 1080p 就如实告诉用户，别硬说下载成功了。

## 排障决策树

```
下载失败
├─ 五个客户端全灭？
│   ├─ 失败很快（几秒内）→ 先看原始输出尾部，很可能是脚本自身参数错误
│   │                       （例如 "No module named --cookies"）
│   ├─ 体检显示无代理     → 开代理软件
│   └─ 体检一切正常       → 换代理节点（家宽/住宅优先）
├─ 只有部分视频失败？
│   └─ IP 信誉不足 → 换节点；或降低画质要求试试
└─ 报 Signature/n challenge solving failed？
    ├─ 确认 Node 已装
    ├─ 确认能访问 github（EJS 组件从那里下载）
    └─ 确认运行环境没注入 NODE_OPTIONS（脚本已自动清除）
```

## 写 yt-dlp 命令时的三个硬性纪律

1. **任何 yt-dlp 参数都不能插在 `-m` 和 `yt_dlp` 之间。**
   命令形如 `python -m yt_dlp <参数>`，参数必须排在 `yt_dlp` 之后。
   插错会报 `No module named --cookies` / `No module named --proxy`，
   表现却像"网络被限流"，极具迷惑性——本项目踩过两次。

2. **跑之前清掉 `NODE_OPTIONS`。** 脚本内部已处理，但如果你自己拼命令，
   务必 `env -u NODE_OPTIONS ...`（某些 agent 环境会给 Node 注入限制 fs 的 shim）。

3. **不要高频重试。** 连续快速请求会把自己打到限流，
   表现为"本来能下的视频现在也下不了"。

## cookie 从哪来

优先用 `Downloads/yt-cookies.txt`——由本项目的 Chrome 扩展
**每 30 分钟自动导出**并覆盖，无需人工干预。脚本会自动在所有候选里
挑 `LOGIN_INFO` 齐全且条数最多的那份。

扩展没装时的兜底顺序：`~/yt-cookies.txt` → `./chrome-cookies.txt`
→ `%APPDATA%\ytdownloader\cookies.txt` → `Downloads/cookies*.txt`

判断是否够用只看一条：**有没有 `LOGIN_INFO`**。
条数多少不重要（扩展导出的 200 条照样能用，手动导出的 400 条里大部分是别的网站的杂项）。
