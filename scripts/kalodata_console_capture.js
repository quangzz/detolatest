/**
 * DETOLA — Kalodata Free-Trial Safe Collector (Zero Export Quota Needed)
 *
 * Hướng dẫn dùng (30 giây):
 * 1. Mở https://www.kalodata.com (tài khoản Free Trial 7 ngày), chọn thị trường Việt Nam.
 * 2. Vào mục Nhà sáng tạo (Creator) -> Lọc ngành Beauty & Personal Care / Chăm sóc da
 *    (hoặc tìm kiếm từ khóa "kem chống nắng"), lọc Follower khoảng 10K - 250K.
 * 3. Nhấn F12 -> tab Console -> Dán toàn bộ đoạn script này vào và nhấn Enter.
 * 4. Bấm chuyển Trang 1, Trang 2, Trang 3... script sẽ tự động gom dồn KOC trong closure cục bộ
 *    mà KHÔNG cần bấm vào từng trang chi tiết (bảo toàn lượt xem chi tiết hàng ngày!).
 * 5. Bấm nút "📥 Tải JSON KOC" để lưu file `kalodata_captured.json` rồi bỏ vào `E:\detola\data\snapshots\`.
 */
(() => {
  const TOOLBAR_ID = "detola-kalodata-capture-toolbar";
  if (document.getElementById(TOOLBAR_ID)) {
    console.info("[DETOLA] Bộ thu thập đang hoạt động trên trang này.");
    return;
  }

  // Đóng gói trạng thái hoàn toàn trong closure cục bộ (không gắn biến debug lên window)
  const kocMap = new Map();

  const updateBadge = () => {
    const btn = document.getElementById("detola-kalodata-dl-btn");
    if (btn) {
      btn.textContent = `📥 Tải JSON KOC (${kocMap.size} KOCs)`;
    }
  };

  // Trích xuất linh hoạt KOC từ bất kỳ object JSON nào của API Kalodata
  const harvestFromObject = (obj) => {
    if (!obj || typeof obj !== "object") return;
    if (Array.isArray(obj)) {
      obj.forEach(harvestFromObject);
      return;
    }
    const possibleHandle =
      obj.uniqueId || obj.unique_id || obj.handle || obj.tiktokHandle || obj.username || obj.secUid;
    const hasMetrics =
      "followerCount" in obj ||
      "followers" in obj ||
      "revenue" in obj ||
      "gmv" in obj ||
      "saleAmount" in obj ||
      "videoRevenue" in obj;

    if (possibleHandle && hasMetrics) {
      const cleanKey = String(possibleHandle).replace(/^@/, "").trim().toLowerCase();
      if (cleanKey && cleanKey.length < 64) {
        const prev = kocMap.get(cleanKey) || {};
        kocMap.set(cleanKey, { ...prev, ...obj, _source: "xhr_api" });
      }
    }
    for (const val of Object.values(obj)) {
      if (val && typeof val === "object") harvestFromObject(val);
    }
  };

  // Quét trực tiếp bảng DOM hiện tại trên màn hình
  const scrapeVisibleDomTable = () => {
    const rows = document.querySelectorAll("tr, .ant-table-row, [class*='table-row']");
    rows.forEach((row) => {
      const text = (row.innerText || "").trim();
      if (!text || text.length < 10) return;

      let handle = "";
      const handleMatch = text.match(/@([a-zA-Z0-9._]{3,40})/);
      if (handleMatch) {
        handle = handleMatch[1].toLowerCase();
      } else {
        const links = row.querySelectorAll("a[href]");
        links.forEach((a) => {
          const href = a.getAttribute("href") || "";
          const m = href.match(/@([a-zA-Z0-9._]{3,40})/);
          if (m && !handle) handle = m[1].toLowerCase();
        });
      }
      if (!handle) return;

      const cells = Array.from(row.querySelectorAll("td, [class*='cell']")).map((c) =>
        (c.innerText || "").replace(/\s+/g, " ").trim()
      );
      const prev = kocMap.get(handle) || {};
      kocMap.set(handle, {
        _source: prev._source || "dom_table",
        handle,
        raw_row_text: text,
        raw_cells: cells,
        ...prev,
      });
    });
    updateBadge();
  };

  // Bắt luồng JSON trả về khi người dùng phân trang/lọc trên giao diện Kalodata
  const origFetch = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const resp = await origFetch(...args);
    try {
      const clone = resp.clone();
      const ct = clone.headers.get("content-type") || "";
      if (ct.includes("application/json")) {
        clone
          .json()
          .then((data) => {
            harvestFromObject(data);
            updateBadge();
          })
          .catch(() => {});
      }
    } catch (_) {}
    return resp;
  };

  const origSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function (...args) {
    this.addEventListener("load", function () {
      try {
        if (this.responseText && this.responseText.trim().startsWith("{")) {
          const data = JSON.parse(this.responseText);
          harvestFromObject(data);
          updateBadge();
        }
      } catch (_) {}
    });
    return origSend.apply(this, args);
  };

  const wrapper = document.createElement("div");
  wrapper.id = TOOLBAR_ID;
  wrapper.style.cssText =
    "position:fixed;bottom:20px;right:20px;z-index:999999;display:flex;gap:8px;font-family:sans-serif;";

  const scanBtn = document.createElement("button");
  scanBtn.textContent = "🔍 Quét bảng hiện tại";
  scanBtn.style.cssText =
    "background:#1e293b;color:#fff;border:none;padding:10px 14px;border-radius:8px;cursor:pointer;font-weight:600;box-shadow:0 4px 12px rgba(0,0,0,0.25);";
  scanBtn.onclick = () => {
    scrapeVisibleDomTable();
    console.info("[DETOLA] Tổng số KOC thu thập được:", kocMap.size);
  };

  const dlBtn = document.createElement("button");
  dlBtn.id = "detola-kalodata-dl-btn";
  dlBtn.style.cssText =
    "background:#10b981;color:#fff;border:none;padding:10px 16px;border-radius:8px;cursor:pointer;font-weight:700;box-shadow:0 4px 12px rgba(0,0,0,0.25);";
  dlBtn.onclick = () => {
    scrapeVisibleDomTable();
    const payload = {
      is_test: false,
      captured_at: new Date().toISOString(),
      page_url: window.location.href,
      koc_count: kocMap.size,
      items: Array.from(kocMap.values()),
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "kalodata_captured.json";
    a.click();
  };

  wrapper.appendChild(scanBtn);
  wrapper.appendChild(dlBtn);
  document.body.appendChild(wrapper);

  scrapeVisibleDomTable();
  setInterval(scrapeVisibleDomTable, 3000);
  console.info("[DETOLA] Đã kích hoạt bộ thu thập Kalodata Free-Trial an toàn.");
})();
