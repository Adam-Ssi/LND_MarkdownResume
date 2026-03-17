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
  const cssEditor     = document.getElementById("css-editor");
  const previewFrame  = document.getElementById("preview-frame");
  const themeSelect   = document.getElementById("theme-select");
  const loadingBadge  = document.getElementById("loading-badge");
  const wordCount     = document.getElementById("word-count");
  const savedBadge    = document.getElementById("saved-badge");
  const btnResetCss   = document.getElementById("btn-reset-css");

  /* ── State ── */
  const STORAGE_KEY_CONTENT    = "rbuilder_content";
  const STORAGE_KEY_THEME      = "rbuilder_theme";
  const STORAGE_KEY_CUSTOM_CSS = "rbuilder_custom_css";
  let previewDebounceTimer  = null;
  let saveDebounceTimer     = null;
  let activeTab             = "markdown";

  /* ================================================================
     INITIALISATION
     ================================================================ */
  function init() {
    restoreSession();
    updateWordCount();
    refreshPreview();          // initial render
    attachListeners();
    updateCssBadge();
  }

  /* ================================================================
     PERSISTENCE  (localStorage)
     ================================================================ */
  function restoreSession() {
    const savedContent   = localStorage.getItem(STORAGE_KEY_CONTENT);
    const savedTheme     = localStorage.getItem(STORAGE_KEY_THEME);
    const savedCustomCss = localStorage.getItem(STORAGE_KEY_CUSTOM_CSS);

    if (savedContent !== null) editor.value = savedContent;
    if (savedTheme && themeSelect.querySelector(`option[value="${savedTheme}"]`)) {
      themeSelect.value = savedTheme;
    }
    if (savedCustomCss !== null) cssEditor.value = savedCustomCss;
  }

  function saveSession() {
    localStorage.setItem(STORAGE_KEY_CONTENT,    editor.value);
    localStorage.setItem(STORAGE_KEY_THEME,      themeSelect.value);
    localStorage.setItem(STORAGE_KEY_CUSTOM_CSS, cssEditor.value);
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
      body.append("theme",         themeSelect.value);
      body.append("custom_css",    cssEditor.value);

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

    const cssField = document.createElement("input");
    cssField.type  = "hidden";
    cssField.name  = "custom_css";
    cssField.value = cssEditor.value;

    form.appendChild(mdField);
    form.appendChild(themeField);
    form.appendChild(cssField);
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
     THEME CSS LOADER
     ================================================================ */
  async function loadThemeCss() {
    try {
      const res = await fetch(`/theme-css/${themeSelect.value}`);
      if (!res.ok) return;
      cssEditor.value = await res.text();
      updateCssBadge();
      schedulePreview(0);
      scheduleSave(500);
    } catch (err) {
      console.error("Failed to load theme CSS:", err);
    }
  }

  /* ================================================================
     TAB SWITCHING
     ================================================================ */
  function switchTab(tab) {
    activeTab = tab;
    const tabs = document.querySelectorAll(".editor-tab");
    tabs.forEach(btn => {
      const isActive = btn.dataset.tab === tab;
      btn.classList.toggle("editor-tab--active", isActive);
      btn.setAttribute("aria-pressed", isActive ? "true" : "false");
    });

    const onCss = tab === "css";
    editor.toggleAttribute("hidden", onCss);
    cssEditor.toggleAttribute("hidden", !onCss);
    wordCount.style.display    = onCss ? "none"         : "";
    btnResetCss.style.display  = onCss ? "inline-flex"  : "none";

    if (onCss) {
      /* Auto-populate from theme if editor is empty */
      if (!cssEditor.value.trim()) loadThemeCss();
      cssEditor.focus();
    }
  }

  function updateCssBadge() {
    const cssTab = document.querySelector('.editor-tab[data-tab="css"]');
    if (!cssTab) return;
    cssTab.classList.toggle("editor-tab--css-active", cssEditor.value.trim().length > 0);
  }

  /* ================================================================
     EVENT LISTENERS
     ================================================================ */
  function attachListeners() {
    /* Markdown editor input → debounced preview + save */
    editor.addEventListener("input", () => {
      updateWordCount();
      schedulePreview(380);
      scheduleSave(900);
    });

    /* CSS editor input → debounced preview + save + badge */
    cssEditor.addEventListener("input", () => {
      updateCssBadge();
      schedulePreview(380);
      scheduleSave(900);
    });

    /* Tab key → insert spaces in either editor */
    [editor, cssEditor].forEach(el => {
      el.addEventListener("keydown", (e) => {
        if (e.key === "Tab") {
          e.preventDefault();
          const s = el.selectionStart;
          el.value = el.value.substring(0, s) + "  " + el.value.substring(el.selectionEnd);
          el.selectionStart = el.selectionEnd = s + 2;
        }
      });
    });

    /* Editor tab buttons */
    document.addEventListener("click", (e) => {
      const tab = e.target.closest(".editor-tab");
      if (tab) switchTab(tab.dataset.tab);
    });

    /* Reset to theme button */
    btnResetCss.addEventListener("click", loadThemeCss);

    /* Theme change → refresh preview; if on CSS tab, reload theme CSS */
    themeSelect.addEventListener("change", () => {
      localStorage.setItem(STORAGE_KEY_THEME, themeSelect.value);
      if (activeTab === "css") {
        loadThemeCss();   // pulls new theme CSS, triggers preview inside
      } else {
        refreshPreview();
      }
    });

    /* Scroll sync (markdown editor only) */
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
