# 排障手册

这份文档记录了把整套流程调通过程中**实际踩过的坑**。
每一条都标注了「症状 → 真正原因 → 解法」，因为这里的坑普遍具有迷惑性：
表象和根因常常完全不是一回事。

---

## 0. 先做体检，别猜

```bash
python yt_dl.py --diagnose
```

下面所有排查都应该在体检之后进行。

---

## 1. 报 "Sign in to confirm you're not a bot"

这是最典型也最容易被误判的错误。**它不等于 cookie 有问题。**

### 1.1 用完整 cookie 实测也一样失败 → 不是 cookie 的锅

验证方法：找一份确定完整的 cookie（含 `LOGIN_INFO`），直接测：

```bash
python -m yt_dlp --simulate --cookies <完整cookie> "<链接>"
```

如果连它也失败，说明问题在 yt-dlp 侧或网络侧，继续往下看。

### 1.2 缺 EJS 解密组件（最常见）

**症状日志：**

```
WARNING: [youtube] [jsc] Remote component challenge solver script (node) was skipped.
         You can enable the download with --remote-components ejs:github
WARNING: [youtube] Signature solving failed: Some formats may be missing.
WARNING: [youtube] n challenge solving failed
```

**原因：** yt-dlp 新版把签名解密拆成了外部组件（EJS）。
光装 Node 不够，还需要显式启用组件下载。

**解法：**

```
--remote-components ejs:github
```

组件从 GitHub releases 下载，所以机器要能访问 GitHub。

### 1.3 缺 JS 运行时

**症状日志：**

```
WARNING: No supported JavaScript runtime could be found.
         Only deno is enabled by default; to use another runtime add --js-runtimes RUNTIME[:PATH]
```

**解法：** 装 Node.js，并显式指定：

```
--js-runtimes "node:<node.exe 的绝对路径>"
```

注意：即使 Node 在 PATH 里，yt-dlp 默认只启用 deno，必须显式写 `node`。

### 1.4 NODE_OPTIONS 注入（最隐蔽）

**症状日志：**

```
WARNING: [youtube] [jsc] Error solving 2 challenge requests using "node" provider:
         Error running node process (returncode: 1): node:fs:440
         Error: Access to this API has been restricted. Use --allow-fs-read
```

**原因：** 某些 agent 运行环境会给 Node 注入：

```
NODE_OPTIONS=--require ".../node-language-shim.cjs"
```

这个 shim 限制了 fs 访问，导致 EJS 脚本跑不起来 → 签名解不开 → 判你机器人。

**解法：** 跑 yt-dlp 前清掉：

```bash
env -u NODE_OPTIONS python -m yt_dlp ...
```

`yt_dl.py` 内部已经处理了，但如果你自己拼命令，务必记得。

### 1.5 出口 IP 信誉差

**症状：** 体检全绿、cookie 完整，但下载失败；
或者**热门视频能下、冷门视频不能**；或者**昨天能下的视频今天不行**。

**判定方法：** 换个对照视频测。

```bash
python -m yt_dlp --simulate "https://youtu.be/dQw4w9WgXcQ"   # 超热门
python -m yt_dlp --simulate "<你真正想下的>"
```

- 热门能过、目标不能 → IP 信誉不足
- 两个都不能 → 检查上面 1.2 / 1.3 / 1.4

**解法：** 换代理节点。**住宅 / 家宽类型远好于 IDC / VPS。**

判断自己的出口是不是 IDC：

```bash
curl -x http://127.0.0.1:7892 https://ipinfo.io/json
```

看 `org` 字段。出现 `Baxet Group`、`DigitalOcean`、`Hetzner` 这类 hosting 商
基本就是 IDC，YouTube 对这类 IP 的检测明显更严。

---

## 2. "五个客户端全部失败"，而且失败得特别快

几秒内就跑完 5 次重试，几乎可以肯定**不是网络限流**，而是命令本身有问题。

### 2.1 参数插错位置（本项目踩过两次）

**症状：**

```
python.exe: No module named --cookies
python.exe: No module named --proxy
```

**原因：** 命令形如 `python -m yt_dlp <参数>`。
如果参数是插到 `-m` 和 `yt_dlp` 之间（比如用 `cmd[2:2]` 拼接），
Python 会把 `--cookies` 当成模块名。

**解法：** 任何 yt-dlp 参数都必须排在 `yt_dlp` 之后。

### 2.2 抓不到 ERROR 行时报"未知错误"

yt-dlp 的失败不总是以 `ERROR` 开头。脚本里如果只 grep `ERROR`，
就会输出"未知错误"，把真实原因吞掉。

**解法：** 抓不到时，把原始输出尾部打出来。
`yt_dl.py` 已经这么做了。

---

## 3. 下载下来了，但画质不对

**别只看日志里的格式 ID。** itag 和实际分辨率不是固定一对一。

比如 itag `398` 在某个视频上是 720p，在另一个上可能是 1080p。

**必须实测：**

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height -of default=noprint_wrappers=1 "<文件>"
```

**如果低于要求，先查片源有多少：**

```bash
python -m yt_dlp -F "<链接>"
```

片源最高只有 720p 时，下载再多次也拿不到 1080p，如实告诉用户即可。

### 3.1 画质对了，但语言不对

YouTube 现在普遍带**多条配音轨**（auto-dub）。下载日志里音轨如果显示成
`f140-6` 这种**带序号**的形式，说明 yt-dlp 是在多条音轨里挑了一条——
默认选中的未必是你要的语言。

**指定语言时用 `language` 筛选**：

```bash
python yt_dl.py "<链接>" \
  -f "bestvideo[height<=1080]+bestaudio[language^=en]/best[height<=1080]/best"
```

和自动补的 `[ext=m4a]` 兼容，`bestaudio[ext=m4a][language^=en]` 是合法串联。

**交付前看一眼**：

```bash
ffprobe -v error -show_entries stream_tags=language -of default=noprint_wrappers=1 "<文件>"
```

输出 `TAG:language=eng` 才说明是英文轨。

---

## 4. 下载下来了，但没声音

**先确认是不是真的没音轨**：

```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,channels \
  -of default=noprint_wrappers=1 "<文件>"
```

- **完全看不到 `codec_type=audio`** → 真的没音轨，重新下载，检查有没有加 `-x`（只要音频）
- **有音轨，但 `codec_name=opus`** → 这就是原因

### 为什么 Opus 会"没声音"

`yt-dlp` 的 `bestaudio` 默认会挑 **Opus**（`itag 251`，码率比 AAC 高）。
但本项目合并输出的是 **MP4 容器**，而 MP4 里放 Opus 属于边缘用法：

- Windows 自带播放器（电影和电视 / Media Player）→ **有画面没声音**
- QuickTime → 直接不支持
- 部分剪辑软件（剪映、Premiere 旧版本）→ 导入后音频轨丢失
- VLC / PotPlayer / mpv → 正常

### 解法

**首选：让脚本自己挑 AAC。** `yt_dl.py` 默认格式串已经是
`bestvideo+bestaudio[ext=m4a]/...`，你传的 `-f "...+bestaudio..."` 也会被自动
补一份 `bestaudio[ext=m4a]` 分支放在最前，不用手动改。

**已经下好的文件，转一下就行**（视频流不重编码，8 分钟片子约 7 秒）：

```bash
ffmpeg -y -i in.mp4 -c:v copy -c:a aac -b:a 192k -movflags +faststart out.mp4
```

`-movflags +faststart` 顺手把 moov atom 挪到文件头，边下边播更顺。

**想保留 Opus 又想要兼容性**：输出改成 `.mkv`（`--merge-output-format mkv`），
MKV 对 Opus 支持完整，但 Windows 自带播放器仍可能不认。

---

## 5. cookie 相关

### 5.1 怎么判断 cookie 够不够用

只看一条：**有没有 `LOGIN_INFO`**。

```bash
grep LOGIN_INFO yt-cookies.txt
```

条数多少不重要。扩展自动导出的 200 条照样能用；
手动导出的 400 条里大部分是别的网站的杂项 cookie。

### 5.2 Netscape 格式里 `#HttpOnly_` 是数据行，不是注释

解析 cookie 文件时，如果先判断 `line.startswith("#")` 再剥前缀，
HttpOnly 的 `LOGIN_INFO` 会被当成注释行忽略掉。

**正确顺序：先剥 `#HttpOnly_` 前缀，再判断 `#`。**

这个 bug 会让"cookie 完整性校验"形同虚设——明明已经丢了登录态却不报警。

### 5.3 取 cookie 必须用 `getAll({})`

Chrome 扩展里如果只对单个 URL 取 cookie（`chrome.cookies.getAll({url})`），
会漏掉 host-only 域（不带 www 的 `youtube.com`）上的
`LOGIN_INFO` / `SID` / `HSID` 等登录态。

**必须用 `chrome.cookies.getAll({})` 取整个 profile 的全量。**

### 5.4 Chrome 新的 App-Bound Encryption

Chrome 127+ 引入了 App-Bound Encryption，`--cookies-from-browser chrome`
在 Windows 上基本必然失败（`Could not copy Chrome cookie database`）。

**结论：** 外部进程直接读 Chrome 的 cookie 数据库这条路已经走不通了。
只能通过 Chrome 自身 —— **扩展 API** 或 **CDP**。本项目用的是扩展 API。

---

## 6. 网络 / 代理

### 6.1 系统代理开着但代理软件没运行

**症状：** 所有请求秒失败，或者 DNS 被污染。

**检查：**

```bash
nslookup www.youtube.com      # 如果解析到 104.244.42.197 这类地址，就是被污染了
```

Windows 上常见情况：系统代理开关是开的、指向 `127.0.0.1:7892`，
但 Clash 根本没启动 —— 等于把流量发往一个没人监听的端口。

**解法：** 启动代理软件，确认端口真的在监听。

### 6.2 探测端口"开着"但判定不可用

只 `connect()` 成功不够，得做真实连通性验证。
但验证时：

- **别只试 google.com** —— 很多代理规则会单独拦/放 Google 域名，造成误判
- **超时别设太短** —— 代理首次建连 + TLS 握手常常要几秒，4 秒会大面积误判

本项目用多个中立目标（cloudflare / gstatic / 1.1.1.1）依次尝试，默认超时 8 秒。

### 6.3 别高频重试

连续快速请求会把自己打到限流，表现为"本来能下的视频现在也下不了"。

`yt_dl.py` 的重试间隔是递增的 5/10/15/20 秒，不要改小。

---

## 7. 报"找不到 yt-dlp"，但其实装过

**症状：**

```
错误：找不到 yt-dlp。请先执行： pip install -U yt-dlp
```

**真正原因：用错了 python。** yt-dlp 装在某个虚拟环境里（比如
`~/.workbuddy/binaries/python/envs/default/`），而你跑脚本用的是另一个 python。
那个 venv 的 `Scripts` 目录不在 PATH 里，`which yt-dlp` 自然找不到。

这个报错极具误导性 —— 它会让你以为没装，白白重装一遍，装完可能还是用错 python。

**解法：** 用装了 yt-dlp 的那个 python 跑脚本。

```bash
# 先确认哪个 python 装了
<候选python> -m yt_dlp --version

# 然后用它跑脚本
"<那个python>" yt_dl.py "<链接>"
```

`yt_dl.py` 现在会自动扫一遍常见 venv，找不到时直接打印"本机另一个 python 装了
（版本 X）：<路径>"，照着复制即可。

**如果确实没装：**

```bash
python -m pip install -U yt-dlp
```

装完记住是装在**哪个** python 下的，以后就用那个 python 跑脚本。

---

## 8. 排查顺序建议

```
1. python yt_dl.py --diagnose        # 看环境
2. python yt_dl.py --simulate <链接>  # 只解析，不加剧限流
3. 失败 → 对照一个超热门视频         # 区分 IP 问题 vs 视频问题
4. 换代理节点（家宽/住宅优先）
5. 还不行 → 翻原始输出尾部，看有没有 1.2 / 1.3 / 1.4 / 2.1 的日志
```
