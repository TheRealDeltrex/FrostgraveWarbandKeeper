// D7: tiny dependency-free text filter shared by the Lexicon search box and
// the hire catalog filter. Given a text input and a container, hides entries
// under `itemSelector` whose text doesn't match, auto-opens their ancestor
// <details> so a match isn't hidden inside a collapsed section, and shows a
// "no matches" note when nothing in the container matched.
(function () {
  function normalize(s) {
    return (s || "").toLowerCase();
  }

  function openAncestors(el) {
    var d = el.closest("details");
    while (d) {
      d.open = true;
      d = d.parentElement ? d.parentElement.closest("details") : null;
    }
  }

  function initFilter(input, root, opts) {
    if (!input || !root) return;
    opts = opts || {};
    var selector = opts.itemSelector || ".spell-row, .item-row, table tbody tr:not(.info-desc-row)";

    var note = document.createElement("p");
    note.className = "muted filter-no-match";
    note.textContent = "No matches.";
    note.style.display = "none";
    root.appendChild(note);

    function apply() {
      var q = normalize(input.value).trim();
      var items = root.querySelectorAll(selector);
      var anyVisible = false;
      items.forEach(function (item) {
        var text = normalize(item.dataset.filterText || item.textContent);
        var match = !q || text.indexOf(q) !== -1;
        item.classList.toggle("filter-hidden", !match);
        // Soldier/bestiary tables pair a row with a following description row
        // ("Info" toggle content) — keep it in lockstep with the row above.
        var next = item.nextElementSibling;
        if (next && next.classList.contains("info-desc-row")) {
          next.classList.toggle("filter-hidden", !match);
        }
        if (match) {
          anyVisible = true;
          if (q) openAncestors(item);
        }
      });
      note.style.display = q && !anyVisible ? "" : "none";
    }

    input.addEventListener("input", apply);
  }

  window.fgInitFilter = initFilter;
})();
