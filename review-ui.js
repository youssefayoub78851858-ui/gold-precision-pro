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
      const price = document.getElementById("gold-live-price");
      const priceUpdated = document.getElementById("gold-price-updated");
      const priceChecked = document.getElementById("gold-price-checked");
      const priceSource = document.getElementById("gold-price-source");
      priceChecked.textContent = typeof data.observedUTC === "string" ? "وقت آخر فحص: " + data.observedUTC : "وقت الفحص غير متاح.";
      const m15 = data.dataStatus === "FRESH" ? data.candles?.["15min"] : null;
      if (m15 && Number.isFinite(m15.close) && m15.close > 0 && typeof m15.closeUTC === "string") {
        price.textContent = "$" + m15.close.toLocaleString("en-US", {minimumFractionDigits:2, maximumFractionDigits:2});
        priceUpdated.textContent = "آخر إغلاق شمعة M15: " + m15.closeUTC;
        priceSource.textContent = "من وسيط البيانات المشترك؛ إغلاق شمعة وليس سعراً لحظياً.";
      } else {
        price.textContent = "غير متاح";
        priceUpdated.textContent = "لا يوجد تحديث سعر موثّق في هذه المحاولة.";
        priceSource.textContent = data.dataStatus === "STANDBY" ? "الخدمة في وضع Standby؛ جلب البيانات متوقف." : "لا تُعرض أسعار تجريبية على أنها مباشرة.";
      }
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
