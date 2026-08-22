/*
 * Tria紹介サイト 共通JS
 * - GA4読み込み(測定IDを設定するまで何も読み込まない)
 * - affiliate_click / code_copy イベント計測
 * 設定手順は tria/SPEC.md §7 を参照。
 */

// ★ここをGA4の測定ID(例 "G-ABC1234XYZ")に差し替えるとGA4が有効になる
var GA4_ID = "G-XXXXXXXXXX";

(function () {
  "use strict";

  var ga4Enabled = /^G-[A-Z0-9]+$/.test(GA4_ID) && GA4_ID.indexOf("XXXX") === -1;

  window.dataLayer = window.dataLayer || [];
  function gtag() { window.dataLayer.push(arguments); }
  window.gtag = window.gtag || gtag;

  if (ga4Enabled) {
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + GA4_ID;
    document.head.appendChild(s);
    gtag("js", new Date());
    gtag("config", GA4_ID);
  }

  function track(eventName, params) {
    if (!ga4Enabled) return;
    params = params || {};
    params.page_path = location.pathname;
    params.transport_type = "beacon";
    window.gtag("event", eventName, params);
  }

  // 紹介リンククリック計測(data-cta属性を持つ<a>)
  document.addEventListener("click", function (e) {
    var a = e.target.closest ? e.target.closest("a[data-cta]") : null;
    if (a) {
      track("affiliate_click", { link_location: a.getAttribute("data-cta") });
    }
  });

  // 招待コードのコピー
  document.addEventListener("click", function (e) {
    var btn = e.target.closest ? e.target.closest("button[data-copy]") : null;
    if (!btn) return;
    var text = btn.getAttribute("data-copy");
    function done() {
      var label = btn.textContent;
      btn.textContent = "コピーしました";
      setTimeout(function () { btn.textContent = label; }, 1600);
      track("code_copy", {});
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, function () {});
    } else {
      var ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); done(); } catch (err) {}
      document.body.removeChild(ta);
    }
  });
})();
