"use strict";
(function () {
  const button = document.getElementById("analyze-v2-button");
  const connection = document.getElementById("connection-state");
  const signal = document.getElementById("decision-state");
  const detail = document.getElementById("decision-detail");
  const status = document.getElementById("gold-analysis-status");
  const results = document.getElementById("gold-analysis-results");
  let pending = false;
  status.textContent = "V3 بحثي عند الطلب فقط؛ لا تنفيذ أو جلب تلقائي للأسعار.";
  button.addEventListener("click", async function () {
    if (pending) return;
    pending = true; button.disabled = true;
    signal.textContent = "—"; connection.textContent = "جارٍ فحص V3";
    results.replaceChildren();
    try {
      const response = await fetch(window.GOLD_API_BASE + "/api/v3/research", {
        cache:"no-store", signal:AbortSignal.timeout(45000)
      });
      const data = await response.json();
      const states = ["FRESH", "STALE", "INVALID", "UNAVAILABLE", "MARKET_CLOSED", "STANDBY"];
      if (data.engine !== "V3" || data.signal !== "WAIT" || data.executable !== false ||
          !states.includes(data.dataStatus) || typeof data.reason !== "string" || !data.reason ||
          (!response.ok && !["UNAVAILABLE", "STANDBY"].includes(data.dataStatus))) {
        throw new Error("استجابة غير متوافقة مع محرك V3 البحثي");
      }
      signal.textContent = "WAIT";
      connection.textContent = data.dataStatus === "FRESH" ? "V3: بيانات متحققة" : "V3: التحليل محجوب";
      detail.textContent = data.dataStatus + " | " + data.reason;
      status.textContent = "V3 بحثي: WAIT | " + detail.textContent;
      for (const frame of ["15min", "1h", "4h"]) {
        const c = data.candles?.[frame];
        const p = document.createElement("p");
        p.textContent = frame + ": " + (c ? "إغلاق " + c.closeUTC + " | العمر بعد الإغلاق " + c.ageAfterCloseSeconds + " ثانية" : "لا توجد شمعة متحققة");
        results.appendChild(p);
      }
      if (data.candidate && data.candidate !== "NONE") {
        const p = document.createElement("p");
        p.textContent = "مرشح بحثي فقط: " + data.candidate + "؛ ليس إشارة تداول.";
        results.appendChild(p);
      }
    } catch (error) {
      signal.textContent = "WAIT";
      connection.textContent = "لا توجد بيانات V3 متحققة";
      status.textContent = detail.textContent = "التحليل محجوب: " + error.message;
      results.replaceChildren();
    } finally {
      document.getElementById("output").textContent = status.textContent;
      pending = false; button.disabled = false;
    }
  });
})();
