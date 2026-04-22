import base64
import json
from bs4 import BeautifulSoup
import time

from aqt import mw
from aqt.editor import Editor
from aqt.webview import AnkiWebView
from aqt.qt import QDialog, QVBoxLayout

from . import config
from . import utils
from . import starter_code  

class CodeMirrorWebView(AnkiWebView):
    def __init__(self, parent=None):
        super().__init__(parent)

    def bundledScript(self, fname: str) -> str:
        if "codemirror/" in fname or "scripts/" in fname:
            return f'<script src="{utils.WEB_PATH}/{fname}"></script>'
        return super().bundledScript(fname)

    def bundledCSS(self, fname: str) -> str:
        if "codemirror/" in fname or "styles/" in fname:
            return f'<link rel="stylesheet" type="text/css" href="{utils.WEB_PATH}/{fname}">'
        return super().bundledCSS(fname)

class CodeMirrorDialog(QDialog):
    def __init__(self, parent, editor: Editor, initial_code: str = "", block_id: str = None):
        super().__init__(parent)
        self.editor = editor
        self.initial_code = initial_code
        self.block_id = block_id

        # --- Basic Window Setup ---
        self.setWindowTitle("Code Editor")
        self.resize(900, 700)
        self.setLayout(QVBoxLayout(self))
        self.layout().setContentsMargins(0, 0, 0, 0)
        
        # --- Webview and Bridge Setup ---
        self.web = CodeMirrorWebView(self)
        self.web.set_bridge_command(self._on_bridge_cmd, self)

        # --- Configuration Loading ---
        self.active_theme = config.CONFIG.get(config.CONFIG_KEY_GLOBAL_THEME, 'dracula')
        last_lang = mw.col.conf.get("anki_codemirror_last_lang", "python")
        button_text = "Update Code" if self.block_id else "Insert Code"

        self.active_theme_css = ""
        theme_path = utils.USER_FILES_PATH / "codemirror" / "theme" / f"{self.active_theme}.css"
        if theme_path.exists():
            self.active_theme_css = theme_path.read_text(encoding="utf-8")

        # --- Asset Loading ---
        supported_langs = config.CONFIG.get(config.CONFIG_KEY_LANGUAGES, ["python", "javascript", "clike", "css", "htmlmixed"])

        # SAFEGUARD: Only load scripts that actually exist to prevent JS crashing
        valid_langs = []
        for lang in supported_langs:
            mode_path = utils.USER_FILES_PATH / "codemirror" / "mode" / lang / f"{lang}.js"
            if mode_path.exists():
                valid_langs.append(lang)

        css_files = [
            "codemirror/lib/codemirror.css",
            "codemirror/addon/dialog/dialog.css",
            f"codemirror/theme/{self.active_theme}.css",
            "styles/styles.css"
        ]
        
        js_files = [
            "codemirror/lib/codemirror.js", 
            "codemirror/addon/edit/closebrackets.js",
            "codemirror/addon/edit/matchbrackets.js", 
            "codemirror/keymap/vim.js", 
            "codemirror/addon/dialog/dialog.js"
        ]
        
        for lang in valid_langs:
            js_files.append(f"codemirror/mode/{lang}/{lang}.js")
            
        js_files.append("scripts/script.js")

        # --- HTML and Initial Data Injection ---
        html_file = utils.USER_FILES_PATH / "codemirror_index.html"
        html_content = html_file.read_text(encoding="utf-8")
        soup = BeautifulSoup(html_content, "html.parser")
        
        textarea = soup.find("textarea", {"id": "code-editor"})
        if textarea and self.initial_code:
            try:
                decoded_initial_code = base64.b64decode(self.initial_code).decode("utf-8")
                textarea.string = decoded_initial_code
            except Exception:
                textarea.string = "Error decoding code."

        # --- DYNAMICALLY BUILD DROPDOWN IN PYTHON ---
        select_tag = soup.find("select", {"id": "language-selector"})
        if select_tag:
            select_tag.clear() # Wipe hardcoded HTML options
            
            mode_mapping = {
                "python": [{"label": "Python", "mode": "python"}],
                "javascript": [{"label": "JavaScript", "mode": "javascript"}],
                "clike": [
                    {"label": "C", "mode": "text/x-csrc"},
                    {"label": "C++", "mode": "text/x-c++src"},
                    {"label": "Java", "mode": "text/x-java"},
                    {"label": "C#", "mode": "text/x-csharp"},
                    {"label": "Objective-C", "mode": "text/x-objectivec"}
                ],
                "css": [{"label": "CSS", "mode": "css"}],
                "htmlmixed": [{"label": "HTML", "mode": "htmlmixed"}],
                "ruby": [{"label": "Ruby", "mode": "ruby"}],
                "sql": [{"label": "SQL", "mode": "sql"}],
                "xml": [{"label": "XML", "mode": "xml"}],
                "go": [{"label": "Go", "mode": "go"}],
                "rust": [{"label": "Rust", "mode": "rust"}],
                "php": [{"label": "PHP", "mode": "php"}],
                "swift": [{"label": "Swift", "mode": "swift"}]
            }
            
            for lang in valid_langs:
                options = mode_mapping.get(lang, [{"label": lang.capitalize(), "mode": lang}])
                for opt in options:
                    option_tag = soup.new_tag("option", value=opt["mode"])
                    option_tag.string = opt["label"]
                    # Auto-select the user's last used language
                    if opt["mode"] == last_lang:
                        option_tag["selected"] = "selected"
                    select_tag.append(option_tag)

        body_content = soup.body.decode_contents() if soup.body else ""

        init_script = f"""<script>
            window.CM_CONFIG = {{
                buttonText: {json.dumps(button_text)},
                language: {json.dumps(last_lang)},
                activeTheme: {json.dumps(self.active_theme)},
                starterCode: {json.dumps(starter_code.STARTER_CODE)}
            }};
        </script>"""

        self.web.stdHtml(body=body_content, css=css_files, js=js_files, context=self, head=init_script)
        self.layout().addWidget(self.web)

    def _on_bridge_cmd(self, cmd: str):
        if cmd.startswith("set_lang:"):
            _, lang = cmd.split(":", 1)
            mw.col.conf["anki_codemirror_last_lang"] = lang
            return

        if cmd.startswith("insert_code:"):
            _, lang, encoded_raw, encoded_html = cmd.split(":", 3)
            decoded_html = base64.b64decode(encoded_html).decode("utf-8")
            
            cm_base_css = (utils.USER_FILES_PATH / "codemirror/lib/codemirror.css").read_text(encoding="utf-8")
            
            css_to_inject = f"""
                {cm_base_css}
                {self.active_theme_css}
                .anki-code-block {{
                    display: inline-block;
                    vertical-align: middle;
                    height: auto;
                    border-radius: 6px;
                    padding: 4px 8px;
                    padding-left: 2em;
                    font-family: 'Fira Code', monospace;
                    font-size: 16px;
                    max-width: 100%;
                    overflow-x: auto;
                    text-align: left;
                }}
            """
            
            self.editor.web.setFocus()

            if self.block_id:
                js_injector = f"""
                (() => {{
                    const shadowRoot = document.activeElement?.shadowRoot;
                    if (!shadowRoot) return;
                    const block = shadowRoot.getElementById('{self.block_id}');
                    if (block) {{
                        block.dataset.rawCode = {json.dumps(encoded_raw)};
                        block.dataset.language = {json.dumps(lang)};
                        block.querySelector('.CodeMirror-code').innerHTML = {json.dumps(decoded_html)};
                    }}
                }})();
                """
            else:
                unique_id = f"code-block-{time.time_ns()}"
                theme_class = f"cm-s-{self.active_theme}"
                
                html_to_insert = f"""
                <span id="{unique_id}" 
                      class="anki-code-block CodeMirror {theme_class}" 
                      contenteditable="false" 
                      data-raw-code="{encoded_raw}"
                      data-language="{lang}">
                    <div class="CodeMirror-code">{decoded_html}</div>
                </span><br>
                """
                
                js_injector = f"""
                (() => {{
                    setTimeout(() => {{
                        if (window.selectionSaver) {{ window.selectionSaver.restore(); }}
                        document.execCommand('insertHTML', false, {json.dumps(html_to_insert)});
                        const shadowRoot = document.activeElement?.shadowRoot;
                        if (!shadowRoot) return;
                        
                        if (!window.ankiCodeBlockListenerAttached) {{
                            shadowRoot.addEventListener('dblclick', (event) => {{
                                const codeBlock = event.target.closest('.anki-code-block');
                                if (codeBlock) {{
                                    pycmd(`edit_code:${{codeBlock.id}}:${{codeBlock.dataset.rawCode}}`);
                                }}
                            }});
                            window.ankiCodeBlockListenerAttached = true;
                        }}

                        const styleId = 'codemirror-syntax-styles';
                        let style = shadowRoot.getElementById(styleId);
                        if (!style) {{
                            style = document.createElement('style');
                            style.id = styleId;
                            shadowRoot.appendChild(style);
                        }}
                        style.innerHTML = {json.dumps(css_to_inject)};
                    }}, 50);
                }})();
                """
            
            self.editor.web.eval(js_injector)
            self.accept()
