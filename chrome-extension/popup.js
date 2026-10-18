document.addEventListener("DOMContentLoaded", async () => {
  const s = await chrome.storage.local.get(["lastExport", "count", "hasLogin"]);
  const el = (id) => document.getElementById(id);

  if (s.lastExport) {
    const d = new Date(s.lastExport);
    el("time").textContent = d.toLocaleString("zh-CN");
  }
  el("count").textContent = s.count != null ? s.count + " 条" : "-";

  const loginEl = el("login");
  if (s.hasLogin === true) {
    loginEl.textContent = "已登录（含 LOGIN_INFO）";
    loginEl.className = "ok";
  } else if (s.hasLogin === false) {
    loginEl.textContent = "未登录，请在 Chrome 登录 Google";
    loginEl.className = "bad";
  } else {
    loginEl.textContent = "-";
  }

  document.getElementById("export").addEventListener("click", async () => {
    const btn = document.getElementById("export");
    btn.disabled = true;
    btn.textContent = "导出中…";
    const res = await chrome.runtime.sendMessage({ action: "export" });
    btn.disabled = false;
    btn.textContent = res && res.ok ? "已导出 ✓" : "立即导出一次";
    setTimeout(() => { window.close(); }, 900);
  });
});
