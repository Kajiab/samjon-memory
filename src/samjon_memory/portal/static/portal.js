/* Samjon Memory Core Portal - progressive enhancement only.
 * All functionality works without JavaScript; this script only improves
 * keyboard focus and character counters.
 */
(function () {
  "use strict";

  function ready(fn) {
    if (document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener("DOMContentLoaded", fn);
    }
  }

  ready(function () {
    // Make the page heading reachable for screen-reader users without
    // stealing the document scroll position.
    var h1 = document.querySelector("h1");
    if (h1) {
      h1.setAttribute("tabindex", "-1");
    }

    // Character counters for bounded text fields. Each form field renders an
    // <output class="counter" data-for="fieldName"> that we keep in sync.
    var counters = document.querySelectorAll("output.counter[data-for]");
    var textareas = document.querySelectorAll("textarea");
    Array.prototype.forEach.call(counters, function (out) {
      var name = out.getAttribute("data-for") || "";
      var field = null;
      Array.prototype.forEach.call(textareas, function (ta) {
        if (ta.getAttribute("name") === name) {
          field = ta;
        }
      });
      if (!field) {
        return;
      }
      var max = parseInt(field.getAttribute("maxlength") || "0", 10) || 0;
      var update = function () {
        out.textContent = field.value.length + (max ? "/" + max : "");
      };
      field.addEventListener("input", update);
      update();
    });

    // Focus the first empty field on edit/create surfaces (forms with a
    // fieldset). This is a no-op when JavaScript is disabled.
    var fieldsets = document.querySelectorAll("fieldset");
    Array.prototype.forEach.call(fieldsets, function (fs) {
      var inputs = fs.querySelectorAll(
        'input:not([type="hidden"]), textarea, select'
      );
      var first = null;
      Array.prototype.forEach.call(inputs, function (el) {
        if (!first && !el.value && !el.disabled) {
          first = el;
        }
      });
      if (first) {
        try {
          first.focus({ preventScroll: true });
        } catch (_e) {
          /* ignore */
        }
      }
    });
  });
})();