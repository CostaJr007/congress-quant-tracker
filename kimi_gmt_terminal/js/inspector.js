/* GMT Inspector: Disabled to keep terminal workspace clean and uncluttered.
   Direct actions (focus asset, open article) are executed directly on click. */
window.GMT = window.GMT || {};
(function (G) {
  "use strict";
  G.inspector = {
    open(type, payload) {
      if (type === "news" && payload && payload.link && payload.link.startsWith("http")) {
        window.open(payload.link, "_blank");
      } else if (type === "stock" && payload && payload.t) {
        if (G.app && G.app.setFocus) G.app.setFocus(payload.t);
      } else if (type === "instrument" && payload && payload.sym) {
        if (G.app && G.app.setFocus) G.app.setFocus(payload.sym);
      }
    },
    close() {
      const ins = document.getElementById("inspector");
      if (ins) {
        ins.classList.remove("open");
        ins.setAttribute("aria-hidden", "true");
      }
    },
    isOpen() {
      const ins = document.getElementById("inspector");
      return ins ? ins.classList.contains("open") : false;
    }
  };
})(window.GMT);
