/* Renewly — small progressive enhancements. No dependencies, no inline script. */
(function () {
  "use strict";

  /* ---- command palette ------------------------------------------------ */
  var dialog = document.getElementById("cmdk");
  var input = document.getElementById("cmdk-input");
  var list = document.getElementById("cmdk-list");
  var empty = document.getElementById("cmdk-empty");
  var rows = list ? Array.prototype.slice.call(list.querySelectorAll(".cmdk__row")) : [];
  var lastFocused = null;

  function paletteLinks(onlyVisible) {
    return rows
      .filter(function (row) {
        return !onlyVisible || !row.hidden;
      })
      .map(function (row) {
        return row.querySelector(".cmdk__item");
      })
      .filter(Boolean);
  }

  function applyFilter(query) {
    var needle = (query || "").trim().toLowerCase();
    var visible = 0;
    rows.forEach(function (row) {
      var link = row.querySelector(".cmdk__item");
      var haystack = (link && link.getAttribute("data-cmdk-label")) || "";
      var matches = !needle || haystack.indexOf(needle) !== -1;
      row.hidden = !matches;
      if (matches) {
        visible += 1;
      }
    });
    if (empty) {
      empty.hidden = visible !== 0;
    }
  }

  function openPalette() {
    if (!dialog || dialog.open) {
      return;
    }
    lastFocused = document.activeElement;
    if (typeof dialog.showModal === "function") {
      dialog.showModal();
    } else {
      dialog.setAttribute("open", "open");
    }
    if (input) {
      input.value = "";
      applyFilter("");
      input.focus();
    }
  }

  function closePalette() {
    if (!dialog || !dialog.open) {
      return;
    }
    dialog.close();
    if (lastFocused && typeof lastFocused.focus === "function") {
      lastFocused.focus();
    }
  }

  Array.prototype.forEach.call(document.querySelectorAll("[data-cmdk-open]"), function (button) {
    button.addEventListener("click", openPalette);
  });
  Array.prototype.forEach.call(document.querySelectorAll("[data-cmdk-close]"), function (button) {
    button.addEventListener("click", closePalette);
  });

  if (dialog) {
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) {
        closePalette();
      }
    });
    dialog.addEventListener("keydown", function (event) {
      if (!input) {
        return;
      }
      var links = paletteLinks(true);
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        if (!links.length) {
          return;
        }
        event.preventDefault();
        var current = links.indexOf(document.activeElement);
        var next =
          event.key === "ArrowDown"
            ? (current + 1) % links.length
            : (current - 1 + links.length) % links.length;
        links[next].focus();
      } else if (event.key === "Enter") {
        if (document.activeElement && document.activeElement.classList.contains("cmdk__item")) {
          return; // let the focused link activate natively
        }
        if (links.length) {
          event.preventDefault();
          window.location.assign(links[0].getAttribute("href"));
        }
      }
    });
  }

  if (input) {
    input.addEventListener("input", function () {
      applyFilter(input.value);
    });
  }

  document.addEventListener("keydown", function (event) {
    var key = event.key || "";
    if ((event.metaKey || event.ctrlKey) && (key === "k" || key === "K")) {
      event.preventDefault();
      if (dialog && dialog.open) {
        closePalette();
      } else {
        openPalette();
      }
    } else if (key === "Escape" && dialog && dialog.open) {
      closePalette();
    }
  });

  /* ---- show/hide password --------------------------------------------- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-pw-toggle]"), function (button) {
    var field = document.getElementById(button.getAttribute("data-pw-toggle"));
    if (!field) {
      return;
    }
    button.addEventListener("click", function () {
      var showing = field.type === "text";
      field.type = showing ? "password" : "text";
      button.textContent = showing ? "Show" : "Hide";
      button.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  });

  /* ---- one-click demo credentials ------------------------------------- */
  Array.prototype.forEach.call(document.querySelectorAll("[data-fill-demo]"), function (button) {
    button.addEventListener("click", function () {
      var email = document.getElementById("email");
      var password = document.getElementById("password");
      if (email) {
        email.value = "cenius@cenius.ai";
      }
      if (password) {
        password.value = "cenius";
      }
      if (email) {
        email.focus();
      }
    });
  });

  /* ---- destructive confirm + double-submit guard ---------------------- */
  function guardForm(form) {
    form.addEventListener("submit", function (event) {
      var message = form.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
        return;
      }
      var submitter = form.querySelector("button[type='submit']");
      if (submitter) {
        window.setTimeout(function () {
          submitter.disabled = true;
        }, 0);
      }
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("form"), guardForm);
})();
