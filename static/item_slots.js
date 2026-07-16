/**
 * Item slots: short primary list; Potion/Scroll/Grimoire open a second dropdown
 * for the specific type. Free text remains for custom items.
 * 2H weapons occupy two slots; unselect clears both.
 */
(function () {
  function isTwoHandedName(name) {
    const n = (name || "").trim().toLowerCase();
    return (
      n === "two-handed weapon" ||
      /two-?handed/.test(n) ||
      /\b2h\b/.test(n) ||
      /2-?handed/.test(n)
    );
  }

  function readJson(id) {
    const el = document.getElementById(id);
    if (!el) return [];
    try {
      return JSON.parse(el.textContent || "[]");
    } catch (e) {
      return [];
    }
  }

  function initBlock(root) {
    const n = parseInt(root.dataset.count, 10) || 0;
    const prefix = root.dataset.prefix || "";
    const potions = readJson(prefix + "-potion-data");
    const spells = readJson(prefix + "-spell-data");
    const picks = [...root.querySelectorAll(".item-slot-pick")];
    const details = [...root.querySelectorAll(".item-slot-detail")];
    const texts = [...root.querySelectorAll(".item-slot-text")];

    function textAt(i) {
      return texts[i];
    }
    function pickAt(i) {
      return picks[i];
    }
    function detailAt(i) {
      return details[i];
    }

    function setText(i, value) {
      if (i < 0 || i >= n) return;
      if (texts[i]) texts[i].value = value;
    }

    function getText(i) {
      return (texts[i] && texts[i].value ? texts[i].value : "").trim();
    }

    function fillDetailOptions(select, kind) {
      select.innerHTML = "";
      const ph = document.createElement("option");
      ph.value = "";
      ph.textContent =
        kind === "potion"
          ? "— choose potion —"
          : kind === "scroll"
            ? "— choose spell on scroll —"
            : "— choose spell in grimoire —";
      select.appendChild(ph);

      if (kind === "potion") {
        potions.forEach((name) => {
          const o = document.createElement("option");
          o.value = name;
          o.textContent = name;
          select.appendChild(o);
        });
      } else {
        spells.forEach((name) => {
          const o = document.createElement("option");
          o.value = name;
          o.textContent = name;
          select.appendChild(o);
        });
      }
    }

    function showMode(i, mode) {
      // mode: 'text' | 'detail'
      const det = detailAt(i);
      const txt = textAt(i);
      if (!det || !txt) return;
      if (mode === "detail") {
        det.hidden = false;
        txt.hidden = true;
        txt.classList.add("item-slot-text-hidden");
      } else {
        det.hidden = true;
        txt.hidden = false;
        txt.classList.remove("item-slot-text-hidden");
      }
    }

    function composedValue(kind, detailVal) {
      if (!detailVal) return kind === "potion" ? "Potion" : kind === "scroll" ? "Scroll" : "Grimoire";
      if (kind === "potion") return detailVal;
      if (kind === "scroll") return "Scroll of " + detailVal;
      if (kind === "grimoire") return "Grimoire of " + detailVal;
      return detailVal;
    }

    function parseStored(value) {
      const v = (value || "").trim();
      if (!v) return { pick: "", kind: "empty", detail: "" };

      // Exact simple / vault option on primary
      const pickEl = pickAt(0);
      if (pickEl) {
        const exact = [...pickEl.options].find(
          (o) => o.value === v && (o.dataset.kind || "simple") !== "potion" &&
            (o.dataset.kind || "") !== "scroll" && (o.dataset.kind || "") !== "grimoire"
        );
        // check any pick for matching simple option
      }
      for (const p of picks) {
        const opt = [...p.options].find((o) => o.value === v);
        if (opt && (opt.dataset.kind || "simple") === "simple") {
          return { pick: v, kind: "simple", detail: "" };
        }
        if (opt && opt.dataset.kind === "vault") {
          return { pick: v, kind: "vault", detail: "" };
        }
      }

      if (potions.includes(v) || /^potion of /i.test(v) ||
          ["Poison", "Explosive Cocktail", "Construct Oil", "Elixir of Speed",
           "Elixir of the Chameleon", "Elixir of Life", "Cordial of Clearsight",
           "Cordial of Empowerment", "Philtre of Fury", "Philtre of Fairy Dust",
           "Bottle of Burrowing", "Bottle of Darkness", "Bottle of Dreams and Nightmares",
           "Bottle of Null", "Ethereal Vacuum", "Shatterstar Draught", "Shrinking Potion"
          ].includes(v)) {
        return { pick: "Potion", kind: "potion", detail: v };
      }
      if (v.startsWith("Scroll of ")) {
        return { pick: "Scroll", kind: "scroll", detail: v.slice("Scroll of ".length) };
      }
      if (v === "Scroll") return { pick: "Scroll", kind: "scroll", detail: "" };
      if (v.startsWith("Grimoire of ")) {
        return { pick: "Grimoire", kind: "grimoire", detail: v.slice("Grimoire of ".length) };
      }
      if (v === "Grimoire") return { pick: "Grimoire", kind: "grimoire", detail: "" };

      // free text / custom
      return { pick: "", kind: "custom", detail: v };
    }

    function applyUiFromText(i) {
      const stored = getText(i);
      const parsed = parseStored(stored);
      const pick = pickAt(i);
      const det = detailAt(i);

      if (parsed.kind === "potion" || parsed.kind === "scroll" || parsed.kind === "grimoire") {
        pick.value = parsed.pick;
        fillDetailOptions(det, parsed.kind);
        // for potions detail value is full name; for scroll/grimoire it's spell name
        if (parsed.kind === "potion") {
          det.value = potions.includes(parsed.detail) ? parsed.detail : "";
        } else {
          det.value = spells.includes(parsed.detail) ? parsed.detail : "";
        }
        showMode(i, "detail");
        // keep composed full value in hidden text field for form submit
        setText(i, stored || composedValue(parsed.kind, det.value));
        // text is hidden but still holds submit value
      } else if (parsed.kind === "simple" || parsed.kind === "vault") {
        pick.value = parsed.pick;
        showMode(i, "text");
        setText(i, stored);
      } else {
        pick.value = "";
        showMode(i, "text");
        setText(i, stored);
      }
    }

    function clearLinkedFlags() {
      texts.forEach((t) => t.classList.remove("item-slot-linked"));
      picks.forEach((p) => p.classList.remove("item-slot-linked"));
      details.forEach((d) => d.classList.remove("item-slot-linked"));
    }

    function refreshLinked() {
      clearLinkedFlags();
      for (let i = 0; i < n - 1; i++) {
        const a = getText(i);
        const b = getText(i + 1);
        if (isTwoHandedName(a) && a && (b === a || !b || b === "—" || b === "(2H)")) {
          if (!b) setText(i + 1, a);
          textAt(i + 1).classList.add("item-slot-linked");
          pickAt(i + 1).classList.add("item-slot-linked");
          detailAt(i + 1).classList.add("item-slot-linked");
          // sync UI of paired slot
          pickAt(i + 1).value = "Two-Handed Weapon";
          showMode(i + 1, "text");
        }
      }
    }

    function clearPairIfTwoHanded(i, previousValue) {
      if (!previousValue || !isTwoHandedName(previousValue)) return;
      if (i + 1 >= n) return;
      const nxt = getText(i + 1);
      if (nxt === previousValue || !nxt || nxt === "—" || nxt === "(2H)") {
        setText(i + 1, "");
        pickAt(i + 1).value = "";
        showMode(i + 1, "text");
      }
    }

    picks.forEach((pick) => {
      pick.addEventListener("change", () => {
        const i = parseInt(pick.dataset.index, 10);
        const previous = getText(i);
        const opt = pick.selectedOptions[0];
        const value = pick.value;
        const kind = opt ? opt.dataset.kind || "simple" : "empty";
        const slotCost = opt ? parseInt(opt.dataset.slots || "1", 10) : 1;
        const det = detailAt(i);

        if (!value) {
          clearPairIfTwoHanded(i, previous);
          setText(i, "");
          showMode(i, "text");
          if (i > 0) {
            const first = getText(i - 1);
            if (first && isTwoHandedName(first) && previous === first) {
              setText(i - 1, "");
              pickAt(i - 1).value = "";
              showMode(i - 1, "text");
            }
          }
          refreshLinked();
          return;
        }

        if (previous && previous !== value && isTwoHandedName(previous)) {
          clearPairIfTwoHanded(i, previous);
        }

        if (kind === "potion" || kind === "scroll" || kind === "grimoire") {
          fillDetailOptions(det, kind);
          det.value = "";
          showMode(i, "detail");
          setText(i, composedValue(kind, ""));
        } else {
          // simple / vault
          showMode(i, "text");
          setText(i, value);
          if (slotCost >= 2) {
            if (i + 1 >= n) {
              alert("Two-handed weapons need two free consecutive slots. Choose an earlier slot.");
              setText(i, "");
              pick.value = "";
              refreshLinked();
              return;
            }
            setText(i + 1, value);
            pickAt(i + 1).value = value;
            showMode(i + 1, "text");
          }
        }
        refreshLinked();
      });
    });

    details.forEach((det) => {
      det.addEventListener("change", () => {
        const i = parseInt(det.dataset.index, 10);
        const pick = pickAt(i);
        const opt = pick.selectedOptions[0];
        const kind = opt ? opt.dataset.kind || "simple" : "simple";
        if (kind === "potion" || kind === "scroll" || kind === "grimoire") {
          setText(i, composedValue(kind, det.value));
        }
      });
    });

    texts.forEach((t) => {
      t.addEventListener("input", () => {
        const i = parseInt(t.dataset.index, 10);
        const val = t.value.trim();
        // free-text mode: leave primary empty for custom, or match option
        const p = pickAt(i);
        if (p && !p.value) {
          // custom typing
        } else if (p) {
          const kind = p.selectedOptions[0]
            ? p.selectedOptions[0].dataset.kind || "simple"
            : "simple";
          if (kind === "simple" || kind === "vault") {
            // keep as-is
          }
        }
        if (!val) {
          refreshLinked();
          return;
        }
        if (isTwoHandedName(val) && i + 1 < n) {
          setText(i + 1, val);
          pickAt(i + 1).value = "Two-Handed Weapon";
          showMode(i + 1, "text");
        }
        refreshLinked();
      });
    });

    // Initialize from existing text values
    for (let i = 0; i < n; i++) {
      applyUiFromText(i);
    }
    refreshLinked();
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll(".item-slots").forEach(initBlock);
  });
})();
