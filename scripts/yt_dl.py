#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yt_dl.py —— 把 YouTube 链接丢进来就下载。

设计目标：**不做任何路径假设**，node / ffmpeg / yt-dlp / 代理端口 / cookie
全部运行时自动探测，拷到任何一台 Windows / macOS / Linux 机器上都能跑。

用法：
    python yt_dl.py <URL> [更多URL...]
    python yt_dl.py <URL> -o ./我的目录
    python yt_dl.py <URL> -f "bestvideo[height<=1080]+bestaudio/best"
    python yt_dl.py <URL> --audio          # 只要音频
    python yt_dl.py <URL> --sub            # 内嵌中英字幕
    python yt_dl.py <URL> --simulate       # 只解析不下载（排障用）
    python yt_dl.py --diagnose             # 环境体检

为什么需要这么一等一的折腾？因为 yt-dlp 下载 YouTube 时最常见的失败
（"Sign in to confirm you're not a bot"）**十有八九跟 cookie 无关**，
而是下面四件事里的某一件没到位，详见 diagnose() 与 docs/TROUBLESHOOTING.md。
"""

import os
import sys
import glob
import time
import socket
import shutil
import platform
import subprocess

IS_WIN = platform.system() == "Windows"

# ---------------------------------------------------------------- 探测工具

def which(cmd):
    return shutil.which(cmd) or shutil.which(cmd + ".exe")


def load_config():
    """读取脚本同目录的 config.json。

    这个文件是给「路径不在常规位置」兜底的（比如 ffmpeg 装在某个自定目录、
    代理端口很特殊）。它不进 Git，仓库里只提供 config.example.json。
    """
    import json
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.isfile(p):
        try:
            return json.load(open(p, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def default_out_dir(cfg=None):
    """默认下载目录。优先级：环境变量 YT_OUTPUT_DIR > config.json 的 output_dir
    > 脚本同目录下的 downloads/。

    想固定下载位置（比如桌面某个文件夹），写进 config.json 最省事，
    之后就不用每次敲 -o 了。
    """
    cfg = cfg if cfg is not None else load_config()
    for v in (os.environ.get("YT_OUTPUT_DIR"), cfg.get("output_dir"), cfg.get("out_dir")):
        if v:
            return os.path.abspath(os.path.expanduser(str(v)))
    return os.path.join(os.getcwd(), "downloads")


def find_node(cfg=None):
    """找 Node（yt-dlp 解 YouTube nsig/sig 签名必须有 JS runtime）。"""
    cfg = cfg or {}
    for key in ("node", "NODE"):
        v = cfg.get(key)
        if v and os.path.isfile(v):
            return v
    v = os.environ.get("YT_NODE")
    if v and os.path.isfile(v):
        return v
    n = which("node")
    if n:
        return n
    cands = []
    if IS_WIN:
        pf = os.environ.get("ProgramFiles", r"C:\Program Files")
        pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        cands += [
            os.path.join(pf, "nodejs", "node.exe"),
            os.path.join(pf86, "nodejs", "node.exe"),
            os.path.join(local, "Programs", "nodejs", "node.exe"),
            os.path.join(local, "fnm_multishells", "node.exe"),
        ]
    elif platform.system() == "Darwin":
        cands += ["/usr/local/bin/node", "/opt/homebrew/bin/node",
                  "/opt/local/bin/node"]
    else:
        cands += ["/usr/bin/node", "/usr/local/bin/node", "/snap/bin/node"]
    for c in cands:
        if os.path.isfile(c):
            return c
    return None


def find_ffmpeg_dir(cfg=None):
    """找 ffmpeg 所在目录（高清格式音视频分离，没有它合并不了）。

    找不到时不会报错，只是高清格式无法合并——所以优先给 config.json 兜底。
    """
    cfg = cfg or {}
    for key in ("ffmpeg_dir", "FFMPEG_DIR"):
        v = cfg.get(key)
        if v and os.path.isdir(v):
            return v
    v = os.environ.get("YT_FFMPEG_DIR") or os.environ.get("FFMPEG_DIR")
    if v and os.path.isdir(v):
        return v
    f = which("ffmpeg")
    if f:
        return os.path.dirname(f)
    cands = []
    if IS_WIN:
        local = os.environ.get("LOCALAPPDATA", "")
        cands += [
            os.path.join(os.environ.get("ProgramData", ""), "chocolatey", "bin"),
            os.path.join(local, "Microsoft", "WinGet", "Links"),
        ]
        # winget / scoop 安装位置带版本号，扫一层
        for base in (os.path.join(local, "Microsoft", "WinGet", "Packages"),
                     os.path.join(local, "Programs")):
            if os.path.isdir(base):
                for d in os.listdir(base):
                    if "ffmpeg" in d.lower():
                        for root, _dirs, files in os.walk(os.path.join(base, d)):
                            if "ffmpeg.exe" in files:
                                cands.append(root)
                                break
    for c in cands:
        exe = "ffmpeg.exe" if IS_WIN else "ffmpeg"
        if os.path.isfile(os.path.join(c, exe)):
            return c
    return None


def find_ytdlp():
    """返回调用 yt-dlp 的命令前缀；找不到返回 None。"""
    try:
        import yt_dlp  # noqa: F401
        return [sys.executable, "-m", "yt_dlp"]
    except ImportError:
        pass
    y = which("yt-dlp")
    if y:
        return [y]
    return None


def python_candidates():
    """本机可能的 python 解释器，用于「当前这个没装 yt-dlp」时兜底去找别的。"""
    seen = []

    def add(p):
        if p and os.path.isfile(p) and p not in seen:
            seen.append(p)

    add(sys.executable)
    for name in ("python3", "python", "py"):
        add(which(name))

    # 常见的 venv 集中位置
    home = os.path.expanduser("~")
    envs = os.path.join(home, ".workbuddy", "binaries", "python", "envs")
    if os.path.isdir(envs):
        try:
            for d in sorted(os.listdir(envs), reverse=True):
                for subdir, exe in (("Scripts", "python.exe"), ("bin", "python")):
                    add(os.path.join(envs, d, subdir, exe))
        except OSError:
            pass

    # 当前目录下的虚拟环境
    for v in (".venv", "venv"):
        for subdir, exe in (("Scripts", "python.exe"), ("bin", "python")):
            add(os.path.join(os.getcwd(), v, subdir, exe))
    return seen


def find_other_python_with_ytdlp(timeout=6):
    """当前 python 没装 yt-dlp 时，扫一遍别的 python 看谁装了。

    这个坑很常见：yt-dlp 装在某个 venv 里，而你随手用了另一个 python 跑脚本，
    脚本就报"找不到 yt-dlp"，让人误以为没装、白白重装一遍。
    """
    for p in python_candidates():
        if os.path.abspath(p) == os.path.abspath(sys.executable):
            continue
        try:
            r = subprocess.run(
                [p, "-c", "import yt_dlp,sys;sys.stdout.write(yt_dlp.version.__version__)"],
                timeout=timeout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                return p, r.stdout.decode("utf-8", "replace").strip()
        except Exception:
            continue
    return None, None


def report_missing_ytdlp():
    """找不到 yt-dlp 时，给出真正有用的提示。"""
    print("错误：当前 python 找不到 yt-dlp。")
    print("  当前 python：%s" % sys.executable)
    print()
    other, ver = find_other_python_with_ytdlp()
    if other:
        print("但本机另一个 python 装了（yt-dlp %s）：" % ver)
        print("  %s" % other)
        print()
        print("直接用它跑本脚本即可：")
        print('  "%s" yt_dl.py "<链接>"' % other)
        print()
        print("（或者把它的 Scripts 目录加进 PATH，之后就不用每次指定全称）")
    else:
        print("本机没找到装了 yt-dlp 的 python，先装一个：")
        print("  %s -m pip install -U yt-dlp" % sys.executable)
    return 2


# 连通性验证目标。不能只试 google.com——很多代理规则会单独拦/放 Google 域名，
# 造成"端口开着却误判为不可用"。多试几个中立目标，任一通过即可。
PROBE_URLS = (
    "https://cp.cloudflare.com/generate_204",
    "https://www.gstatic.com/generate_204",
    "https://1.1.1.1/cdn-cgi/trace",
    "https://www.google.com/generate_204",
)


def _proxy_alive(port, timeout=4):
    import urllib.request
    handler = urllib.request.ProxyHandler({
        "http": "http://127.0.0.1:%d" % port,
        "https": "http://127.0.0.1:%d" % port,
    })
    opener = urllib.request.build_opener(handler)
    for url in PROBE_URLS:
        try:
            r = opener.open(url, timeout=timeout)
            if r.status in (200, 204):
                return True
        except Exception:
            continue
    return False


def detect_proxy(verify=True, timeout=8, cfg=None):
    """探测本机代理端口。

    只 connect 成功还不够——有些端口开着但不放行外网，所以再做一次
    真实连通性验证。

    注意 timeout 别设太小：代理首次建连 + TLS 握手常常要几秒，
    4 秒会大面积误判成"端口开着但不可用"，所以默认给 8 秒。
    """
    cfg = cfg or {}
    for key in ("proxy", "PROXY"):
        v = cfg.get(key)
        if v:
            return v
    v = os.environ.get("YT_PROXY")
    if v:
        return v

    ports = (7892, 7890, 7897, 7891, 10809, 10808, 1080, 2080, 8889, 20171, 2081)
    for port in ports:
        s = socket.socket()
        s.settimeout(0.5)
        try:
            s.connect(("127.0.0.1", port))
        except OSError:
            continue
        finally:
            try:
                s.close()
            except OSError:
                pass
        if not verify:
            return "http://127.0.0.1:%d" % port
        if _proxy_alive(port, timeout):
            return "http://127.0.0.1:%d" % port
    return None


# ---------------------------------------------------------------- cookie 选择

def home():
    return os.path.expanduser("~")


def cookie_candidates():
    """按优先级列出可能的 cookie 文件位置。"""
    c = []
    dl = os.path.join(home(), "Downloads")
    # 本项目的 Chrome 扩展自动导出，固定这个名字
    c.append(os.path.join(dl, "yt-cookies.txt"))
    c.append(os.path.join(home(), "yt-cookies.txt"))
    c.append(os.path.join(os.getcwd(), "chrome-cookies.txt"))
    if IS_WIN:
        c.append(os.path.join(os.environ.get("APPDATA", ""),
                              "ytdownloader", "cookies.txt"))
    # 手动用其他扩展导出的
    c += sorted(glob.glob(os.path.join(dl, "cookies*.txt")),
                key=os.path.getmtime, reverse=True)
    return c


def cookie_quality(path):
    """返回 (是否含 LOGIN_INFO, 数据行数)。

    注意 Netscape 格式里 `#HttpOnly_` 是**数据行**不是注释，
    必须先剥掉前缀再判断 `#`，否则 HttpOnly 的 LOGIN_INFO 会被漏掉。
    """
    try:
        text = open(path, "rb").read().decode("utf-8", "replace")
    except OSError:
        return (False, 0)
    rows, has_login = 0, False
    for line in text.splitlines():
        if not line.strip():
            continue
        body = line[len("#HttpOnly_"):] if line.startswith("#HttpOnly_") else line
        if body.startswith("#"):
            continue
        f = body.split("\t")
        if len(f) >= 7:
            rows += 1
            if f[5].strip() == "LOGIN_INFO":
                has_login = True
    return (has_login, rows)


def pick_cookie():
    best, best_score = None, (-1, -1)
    for p in cookie_candidates():
        if p and os.path.isfile(p):
            q = cookie_quality(p)
            key = (1 if q[0] else 0, q[1])
            if key > best_score:
                best, best_score = p, key
    return best


# ---------------------------------------------------------------- 命令构建

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
CLIENTS = [None, "tv", "web_embedded", "mweb", "web_safari"]


def clean_env(proxy=None):
    """清理会干扰 yt-dlp 的环境变量。

    NODE_OPTIONS 必须清掉：某些 agent 运行环境会给 Node 注入 shim
    （--require .../node-language-shim.cjs），它会限制 fs 访问，
    导致 EJS 解密脚本报 "Access to this API has been restricted"，
    签名解不开 → YouTube 判你机器人。**这一条最隐蔽，也最致命。**
    """
    env = dict(os.environ)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
              "all_proxy", "ALL_PROXY", "NODE_OPTIONS"):
        env.pop(k, None)
    if proxy:
        env["http_proxy"] = env["https_proxy"] = proxy
        env["HTTP_PROXY"] = env["HTTPS_PROXY"] = proxy
    return env


def build_cmd(base, url, out_dir, fmt, client, audio, sub, simulate,
              cookie, node, ffmpeg_dir, proxy):
    cmd = list(base)

    # —— 这三行是成败关键，顺序无所谓但一个都不能少 ——
    if node:
        cmd += ["--js-runtimes", "node:%s" % node]          # ① JS 运行时
    cmd += ["--remote-components", "ejs:github"]            # ② EJS 解密组件
    if ffmpeg_dir:
        cmd += ["--ffmpeg-location", ffmpeg_dir]            # ③ ffmpeg

    cmd += ["--user-agent", UA]
    cmd += ["--add-header", "Accept-Language:en-US,en;q=0.9"]
    cmd += ["--no-playlist"]
    cmd += ["-o", os.path.join(out_dir, "%(title).100s [%(id)s].%(ext)s")]

    if audio:
        cmd += ["-f", "bestaudio/best", "-x", "--audio-format", "m4a"]
    elif fmt:
        # 用户给的格式串里若只写 bestaudio（没限定容器），把含 bestaudio 的分支
        # 各补一份 [ext=m4a] 版本置于最前 —— 见下方 AAC 说明。
        # 按 / 拆分支处理，避免把 fallback 链拼坏。
        if "bestaudio" in fmt and "ext=" not in fmt:
            parts = fmt.split("/")
            m4a_first = [p.replace("bestaudio", "bestaudio[ext=m4a]", 1)
                         for p in parts if "bestaudio" in p]
            fmt = "/".join(m4a_first + parts)
        cmd += ["-f", fmt]
    else:
        # 音轨优先 m4a（AAC）：yt-dlp 默认会挑 Opus（码率更高），但 MP4 里放 Opus
        # 兼容性很差 —— Windows 自带播放器、QuickTime、部分剪辑软件都会"有画面没声音"。
        # YouTube 几乎所有视频都有 AAC 音轨(itag 140)，选它不损失画质也不用重编码。
        cmd += ["-f", "bestvideo+bestaudio[ext=m4a]/bestvideo+bestaudio/best"]
    if not audio:
        cmd += ["--merge-output-format", "mp4"]

    if sub:
        cmd += ["--sub-langs", "zh-Hans,zh-CN,en.*", "--embed-subs"]

    cmd += ["--retries", "5", "--fragment-retries", "5",
            "--concurrent-fragments", "4"]

    if client:
        cmd += ["--extractor-args", "youtube:player_client=%s" % client]
    if simulate:
        cmd += ["--simulate"]
    if proxy:
        # 必须放在 yt-dlp 子命令之后（base 是 [python,-m,yt_dlp] 或 [yt-dlp]）
        cmd += ["--proxy", proxy]
    if cookie:
        cmd += ["--cookies", cookie]

    cmd.append(url)
    return cmd


# ---------------------------------------------------------------- 体检

def quick_overrides(args):
    """体检模式下也要支持 --ffmpeg-dir / --proxy / --node 显式指定。"""
    o = {}
    for i, a in enumerate(args):
        if a == "--ffmpeg-dir" and i + 1 < len(args):
            o["ffmpeg_dir"] = args[i + 1]
        elif a == "--proxy" and i + 1 < len(args):
            o["proxy"] = args[i + 1]
        elif a == "--node" and i + 1 < len(args):
            o["node"] = args[i + 1]
    return o


def diagnose(overrides=None):
    cfg = load_config()
    cfg.update(overrides or {})
    print("=" * 60)
    print(" 环境体检")
    print("=" * 60)

    ok = True
    print("[INFO] 下载到 : %s" % default_out_dir(cfg))

    base = find_ytdlp()
    if base:
        print("[OK]   yt-dlp : %s" % " ".join(base))
    else:
        print("[FAIL] yt-dlp : 当前 python 里没有（%s）" % sys.executable)
        other, ver = find_other_python_with_ytdlp()
        if other:
            print("        但本机另一个 python 装了（yt-dlp %s）：" % ver)
            print("        %s" % other)
            print("        -> 用这个 python 跑本脚本即可，不用重装")
        else:
            print("        -> 先装：%s -m pip install -U yt-dlp" % sys.executable)
        ok = False

    node = find_node(cfg)
    if node:
        print("[OK]   Node   : %s" % node)
    else:
        print("[WARN] Node   : 未找到（解不了 nsig 签名，大概率被判机器人）")
        ok = False

    ff = find_ffmpeg_dir(cfg)
    if ff:
        print("[OK]   ffmpeg : %s" % ff)
    else:
        print("[WARN] ffmpeg : 未找到（高清格式音视频无法合并成 mp4）")
        print("        -> 装好后写进 scripts/config.json 的 ffmpeg_dir 即可")

    cookie = pick_cookie()
    if cookie:
        has_login, rows = cookie_quality(cookie)
        flag = "OK" if has_login else "WARN"
        print("[%s] cookie : %s (%d 条, LOGIN_INFO=%s)"
              % (flag, cookie, rows, "有" if has_login else "无"))
        if not has_login:
            print("        -> Chrome 里登录 Google 后，让扩展重新导出一次")
    else:
        print("[WARN] cookie : 没有找到任何 cookie 文件，将以匿名方式尝试")

    proxy = detect_proxy(cfg=cfg)
    if proxy:
        print("[OK]   代理   : %s" % proxy)
    else:
        print("[WARN] 代理   : 未探测到可用代理端口，将直连")
        print("        -> 国内网络需先开启 Clash 等代理；IDC 出口 IP 也容易被限流")

    if os.environ.get("NODE_OPTIONS"):
        print("[WARN] NODE_OPTIONS: 已注入 %r，脚本运行时会自动清除"
              % os.environ["NODE_OPTIONS"])

    print("=" * 60)
    print("结论：%s" % ("环境就绪，可以下载" if ok else "存在致命项，见上方 [WARN]/[FAIL]"))
    return 0 if ok else 1


# ---------------------------------------------------------------- 下载

def run(url, out_dir, fmt, audio, sub, simulate, overrides=None):
    base = find_ytdlp()
    if not base:
        return report_missing_ytdlp()

    cfg = load_config()
    cfg.update(overrides or {})
    node = find_node(cfg)
    ffmpeg_dir = find_ffmpeg_dir(cfg)
    cookie = pick_cookie()

    if cookie:
        has_login, rows = cookie_quality(cookie)
        print("[cookie] %s  (%d 条, LOGIN_INFO=%s)"
              % (cookie, rows, "有" if has_login else "无"))
    else:
        print("[cookie] 未找到 cookie 文件，将以匿名方式尝试")

    proxy = detect_proxy(cfg=cfg)
    if proxy:
        print("[代理] 使用 %s" % proxy)
    else:
        print("[代理] 未探测到可用代理，将直连（国内网络通常会失败）")

    env = clean_env(proxy)
    os.makedirs(out_dir, exist_ok=True)

    for i, client in enumerate(CLIENTS, 1):
        cmd = build_cmd(base, url, out_dir, fmt, client, audio, sub,
                        simulate, cookie, node, ffmpeg_dir, proxy)
        print("\n[尝试 %d/%d] 播放器客户端 = %s" % (i, len(CLIENTS), client or "默认"))
        proc = subprocess.run(cmd, env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            print("[成功] %s  客户端=%s" % (url, client or "默认"))
            for line in out.splitlines():
                if ("[download] Destination" in line or "[Merger]" in line
                        or "already been downloaded" in line):
                    print("        " + line.strip())
            return 0
        reason = ""
        for line in out.splitlines():
            if line.strip().startswith("ERROR"):
                reason = line.strip()
        if reason:
            print("[失败] %s" % reason[:200])
        else:
            print("[失败] 未识别的错误，原始输出尾部：")
            for line in out.strip().splitlines()[-12:]:
                print("        " + line.strip()[:200])
        if i < len(CLIENTS):
            wait = 5 * i
            print("        等待 %d 秒后换下一个客户端（间隔太短会加剧限流）" % wait)
            time.sleep(wait)

    print("\n[结论] 所有客户端都失败。最常见原因是出口 IP 被限流，")
    print("       建议换一个住宅/家宽类型的代理节点后重试。")
    return 1


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 2
    if any(a in ("--diagnose", "--doctor", "-d") for a in args):
        return diagnose(quick_overrides(args))

    urls, out_dir, fmt = [], default_out_dir(), None
    audio = sub = simulate = False
    overrides = {}

    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-o", "--out"):
            out_dir = args[i + 1]; i += 2
        elif a in ("-f", "--format"):
            fmt = args[i + 1]; i += 2
        elif a in ("--ffmpeg-dir",):
            overrides["ffmpeg_dir"] = args[i + 1]; i += 2
        elif a in ("--proxy",):
            overrides["proxy"] = args[i + 1]; i += 2
        elif a in ("--node",):
            overrides["node"] = args[i + 1]; i += 2
        elif a == "--audio":
            audio = True; i += 1
        elif a == "--sub":
            sub = True; i += 1
        elif a == "--simulate":
            simulate = True; i += 1
        elif a.startswith("-"):
            i += 1
        else:
            urls.append(a); i += 1

    if not urls:
        print("没有给出视频链接")
        return 2

    code = 0
    for u in urls:
        code |= run(u, out_dir, fmt, audio, sub, simulate, overrides)
    return code


if __name__ == "__main__":
    sys.exit(main())
