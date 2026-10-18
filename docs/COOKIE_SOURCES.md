# 抓 cookie 的几条路，为什么选了扩展

浏览器登录态是 yt-dlp 过 bot 校验的关键。但"把浏览器里的 cookie 拿出来"
这件事在 2024 年之后变难了 —— 因为 Chrome 127 引入了 **App-Bound Encryption**。

下面把可选的几条路都摆出来，包括我们不推荐的那几条，以及原因。

## 总览

| 方案 | 要装东西吗 | 自动化 | 结论 |
|---|---|---|---|
| **浏览器扩展**（本项目） | 装一个扩展 | ✅ 每 30 分钟自动导出 | **推荐** |
| yt-dlp 直读浏览器库 | 否 | ✅ 全自动 | Chrome/Edge **已失效**；Firefox 仍可用 |
| CDP 远程调试 | 否 | ⚠️ 需带参数启动浏览器 | 技术上可行，但比装扩展折腾得多 |
| 手动导出 | 否 | ❌ 每次手动点 | 就是本项目要消灭的东西 |

---

## 1. 浏览器扩展（推荐）

扩展跑在浏览器进程内部，通过官方 API `chrome.cookies.getAll({})` 取 cookie。
**浏览器自己把解密后的值交出来**，所以根本不碰 App-Bound Encryption 这一层。

这是目前唯一既全自动、又不依赖任何安全漏洞的路子。

同一份代码在 **Chrome 和 Edge 上都能跑**（Edge 就是 Chromium，MV3 API 完全一致），
manifest.json 一个字都不用改。

---

## 2. `yt-dlp --cookies-from-browser`：Chrome/Edge 上已经废了

这条曾经是最省事的方案，现在不行了。

**原因：** Chrome 127+ 的 App-Bound Encryption 把 cookie 数据库的密钥
交给一个 SYSTEM 权限的服务来解密。外部进程就算把 `Cookies` 文件复制出来，
也拿不到密钥，解不开。

典型报错：

```
ERROR: Could not copy Chrome cookie database
```

注意这个报错**有误导性** —— 听起来像是"文件被占用复制不了"，
实际上就算复制成功也解不开。yt-dlp 的报错是按旧逻辑写的。

**但 Firefox 仍然可用。** Firefox 的 `cookies.sqlite` 没有这层保护：

```bash
python -m yt_dlp --cookies-from-browser firefox "<链接>"
```

**所以：如果你愿意用 Firefox，连扩展都不用装** —— 装个 Firefox、
登录 Google，上面这条命令直接就能跑，零安装零配置。

Firefox 也是唯一一个"外部进程直读 cookie"还没被堵死的浏览器。
不过它的代价是：你得为一个下载流程专门用另一个浏览器登录 Google。

---

## 3. CDP（Chrome DevTools Protocol）：能跑，但折腾

**原理：** 用 `--remote-debugging-port=9222` 启动浏览器，程序连上去调用
`Network.getAllCookies`。cookie 同样是由浏览器进程解密后返回的，
所以也**不受 App-Bound Encryption 限制**，HttpOnly 的 `LOGIN_INFO` 一样拿得到。

**为什么我们没选它：**

1. **浏览器必须以调试端口启动。** 你日常打开的那个 Chrome 没开这个端口，
   CDP 连不上去。想让它生效，就得改快捷方式或者每次用脚本启动，
   等于把日常浏览器长期置于调试模式 —— 安全上不太舒服，
   而且部分网站会检测调试端口的存在。
2. **profile 是个坑。** 如果用 `--user-data-dir` 另起一份 profile，
   那份 profile 里没有你的 Google 登录态，得重新登录一遍。
   如果指向现有 profile，又要跟正在运行的浏览器抢锁。
3. **拿到的是 JSON，不是 Netscape 格式**，还得自己转换。

**什么时候值得用：** 目标机器上什么扩展都装不了（公司策略锁死）、
但你又能控制浏览器启动参数的时候。

最小验证步骤（需要先用这条命令启动浏览器，不能在已运行的实例上追加）：

```bash
chrome.exe --remote-debugging-port=9222
```

```bash
curl http://127.0.0.1:9222/json/version      # 取 webSocketDebuggerUrl
# 然后 WebSocket 发送 {"id":1,"method":"Network.getAllCookies"}
```

> 这条路本项目**没有内置**，也未在真机上验证过（只做了资料层面的确认），
> 列在这里只是把选项说全。真要用，请自己先跑通再依赖它。

---

## 4. 手动导出（我们要消灭的东西）

用 Get cookies.txt LOCALLY 一类扩展，每次点一下、复制、粘贴。
失效了就得重来一遍。这也是本项目最初的起因。

顺带一提：市面这类扩展（Cookie-Editor、EditThisCookie、
Get cookies.txt Clean 等）**全都需要手动点击**，没有一个支持定时自动导出 ——
这也是我们最后选择自己写一个的原因。

---

## 浏览器支持情况

| 浏览器 | 本扩展能装吗 | yt-dlp 直读 | 上架商店费用 |
|---|---|---|---|
| Chrome | ✅ 同一份代码 | ❌ 已失效 | $5 一次性 |
| **Edge** | ✅ 同一份代码，零改动 | ❌ 同样失效 | **免费** |
| Firefox | ⚠️ 需改 manifest | ✅ 可用 | 免费 |

**Edge 细节：** Edge 用的就是 Chromium 的 MV3 API，
`chrome.cookies` / `chrome.downloads` / `chrome.alarms` 全都支持，
`chrome-extension/` 目录原样拿到 `edge://extensions` 里"加载解压缩的扩展"即可。

**Firefox 细节：** Firefox 的 MV3 用 `background.scripts` 而不是 service worker，
命名空间上也更推荐 `browser.*`（虽然兼容 `chrome.*`）。要适配得改 manifest，
本项目暂未做 —— 好在 Firefox 用户可以直接用方案 2，不需要扩展。
