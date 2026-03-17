# **Product Requirements Document: Python Markdown Resume Builder** 

## **1\. Executive Summary**

The **Markdown Resume Builder** is a Python-based utility that enables users to generate high-fidelity, ATS-friendly resumes using plain-text Markdown. By separating data (Markdown) from design (CSS), it ensures that developers can maintain their resumes using the same version-control principles they use for code.

## **2\. Technical Stack**

* **Language:** Python 3.10+  
* **Web Layer:** Flask / FastAPI (Backend) or Reflex (Full-Stack).  
* **Parsing:** `markdown2` with "extras" enabled (tables, code-friendly).  
* **PDF Conversion:** `WeasyPrint` (requires `pango` and `cairo` dependencies).  
* **Styling:** Custom CSS with Google Fonts integration.

## **3\. Functional Requirements**

### **3.1 Live Markdown Editor**

* **Input:** A large, monospaced text field for Markdown entry.  
* **Live Preview:** Real-time (or debounced) HTML rendering using Python’s Markdown libraries.  
* **Sync-Scroll:** Optional synchronization between the editor and the preview pane.

### **3.2 Multi-Theme Engine** 

* **Thematic Stylesheets:** \* **Modern:** Sans-serif fonts, accent colors for headers, 2-column layout.  
  * **Classic:** Serif fonts (Times New Roman style), centered headers, traditional 1-column layout.  
  * **Technical:** Compact layout optimized for long lists of skills and technologies.  
* **CSS Injection:** The system must merge the Markdown-generated HTML with the selected theme's CSS file.

### **3.3 Export & Persistence**

* **PDF Export:** High-resolution PDF generation via WeasyPrint, preserving all styling and hyperlinks.  
* **Live Export:** Option to download the raw Markdown file or the processed HTML.  
* **Local Storage:** (Optional) Use browser local storage to save the Markdown text between sessions.

## **4\. User Interface (UI) Design**

* **Layout:** Split-pane interface.  
  * **Left (40%):** Markdown Editor.  
  * **Right (60%):** Live Document Preview.  
* **Controls:** A top navigation bar or sidebar containing:  
  * Theme Selector (Dropdown).  
  * Template Selector (Professional, Academic, Minimal).  
  * Download Button (Primary Action).
