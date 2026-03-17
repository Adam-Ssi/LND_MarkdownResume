/**
 * Markdown Resume Builder — frontend logic
 *
 * Responsibilities:
 *  - Debounced live preview via POST /preview
 *  - Theme switching
 *  - Load sample templates via GET /template/:name
 *  - Download PDF via form POST to /export
 *  - Persist session to localStorage
 *  - Synchronised scroll (percentage-based)
 */

(function () {
  "use strict";

  /* ── DOM references ── */
  const editor        = document.getElementById("editor");
  const previewFrame  = document.getElementById("preview-frame");
  const themeSelect   = document.getElementById("theme-select");
  const loadingBadge  = document.getElementById("loading-badge");
  const wordCount     = document.getElementById("word-count");
  const savedBadge    = document.getElementById("saved-badge");

  /* ── State ── */
  const STORAGE_KEY_CONTENT = "rbuilder_content";
  const STORAGE_KEY_THEME   = "rbuilder_theme";
  let previewDebounceTimer  = null;
  let saveDebounceTimer     = null;

  /* ================================================================
     INITIALISATION
     ================================================================ */
  function init() {
    restoreSession();
    updateWordCount();
    refreshPreview();          // initial render
    attachListeners();
  }

  /* ================================================================
     PERSISTENCE  (localStorage)
     ================================================================ */
  function restoreSession() {
    const savedContent = localStorage.getItem(STORAGE_KEY_CONTENT);
    const savedTheme   = localStorage.getItem(STORAGE_KEY_THEME);

    if (savedContent !== null) {
      editor.value = savedContent;
    }
    if (savedTheme && themeSelect.querySelector(`option[value="${savedTheme}"]`)) {
      themeSelect.value = savedTheme;
    }
  }

  function saveSession() {
    localStorage.setItem(STORAGE_KEY_CONTENT, editor.value);
    localStorage.setItem(STORAGE_KEY_THEME, themeSelect.value);
    flashSavedBadge();
  }

  function flashSavedBadge() {
    if (!savedBadge) return;
    savedBadge.classList.add("visible");
    clearTimeout(savedBadge._timer);
    savedBadge._timer = setTimeout(() => savedBadge.classList.remove("visible"), 1500);
  }

  /* ================================================================
     WORD COUNT
     ================================================================ */
  function updateWordCount() {
    if (!wordCount) return;
    const words = editor.value.trim().split(/\s+/).filter(Boolean).length;
    wordCount.textContent = `${words} word${words !== 1 ? "s" : ""}`;
  }

  /* ================================================================
     LIVE PREVIEW
     ================================================================ */
  async function refreshPreview() {
    setLoading(true);
    try {
      const body = new FormData();
      body.append("markdown_text", editor.value);
      body.append("theme", themeSelect.value);

      const res  = await fetch("/preview", { method: "POST", body });
      const html = await res.text();

      // Use srcdoc so the preview is sandboxed from the parent page
      previewFrame.srcdoc = html;
    } catch (err) {
      console.error("Preview refresh failed:", err);
    } finally {
      setLoading(false);
    }
  }

  function schedulePreview(delay = 400) {
    clearTimeout(previewDebounceTimer);
    previewDebounceTimer = setTimeout(refreshPreview, delay);
  }

  function scheduleSave(delay = 1000) {
    clearTimeout(saveDebounceTimer);
    saveDebounceTimer = setTimeout(saveSession, delay);
  }

  function setLoading(on) {
    if (!loadingBadge) return;
    loadingBadge.style.opacity = on ? "1" : "0";
  }

  /* ================================================================
     LOAD TEMPLATE
     ================================================================ */
  async function loadTemplate(name) {
    try {
      const res  = await fetch(`/template/${name}`);
      const data = await res.json();
      if (data.content) {
        editor.value = data.content;
        updateWordCount();
        schedulePreview(0);   // immediate render
        scheduleSave(500);
      }
    } catch (err) {
      console.error("Failed to load template:", err);
    }
  }

  /* ================================================================
     PDF EXPORT
     ================================================================ */
  function downloadPDF() {
    const form = document.createElement("form");
    form.method = "POST";
    form.action = "/export";
    form.style.display = "none";

    const mdField = document.createElement("input");
    mdField.type  = "hidden";
    mdField.name  = "markdown_text";
    mdField.value = editor.value;

    const themeField = document.createElement("input");
    themeField.type  = "hidden";
    themeField.name  = "theme";
    themeField.value = themeSelect.value;

    form.appendChild(mdField);
    form.appendChild(themeField);
    document.body.appendChild(form);
    form.submit();
    setTimeout(() => document.body.removeChild(form), 500);
  }

  /* ================================================================
     SYNCHRONISED SCROLL
     Mirrors the editor scroll percentage to the preview iframe.
     ================================================================ */
  function syncScroll() {
    const pct = editor.scrollTop / (editor.scrollHeight - editor.clientHeight || 1);
    try {
      const doc = previewFrame.contentDocument || previewFrame.contentWindow?.document;
      if (!doc) return;
      const maxScroll = doc.documentElement.scrollHeight - doc.documentElement.clientHeight;
      doc.documentElement.scrollTop = pct * maxScroll;
    } catch {
      /* cross-origin srcdoc — safe to ignore */
    }
  }

  /* ================================================================
     EVENT LISTENERS
     ================================================================ */
  function attachListeners() {
    /* Editor input → debounced preview + save */
    editor.addEventListener("input", () => {
      updateWordCount();
      schedulePreview(380);
      scheduleSave(900);
    });

    /* Tab key → insert spaces instead of losing focus */
    editor.addEventListener("keydown", (e) => {
      if (e.key === "Tab") {
        e.preventDefault();
        const s = editor.selectionStart;
        editor.value =
          editor.value.substring(0, s) + "  " + editor.value.substring(editor.selectionEnd);
        editor.selectionStart = editor.selectionEnd = s + 2;
      }
    });

    /* Theme change → immediate refresh */
    themeSelect.addEventListener("change", () => {
      localStorage.setItem(STORAGE_KEY_THEME, themeSelect.value);
      refreshPreview();
    });

    /* Scroll sync */
    editor.addEventListener("scroll", syncScroll);

    /* Template buttons (delegated) */
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-template]");
      if (btn) loadTemplate(btn.dataset.template);

      if (e.target.closest("#btn-export")) downloadPDF();
      if (e.target.closest("#btn-refresh")) refreshPreview();
    });
  }

  /* ── Boot ── */
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
