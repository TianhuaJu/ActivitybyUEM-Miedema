# -*- coding: utf-8 -*-
"""
Chat Widget - 对话式热力学计算界面
==================================
提供自然语言交互的热力学计算界面

作者: Claude
日期: 2026-02-12
"""

import json
import re
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QLineEdit, QScrollArea, QFrame,
    QGroupBox, QSplitter, QMessageBox, QSizePolicy,
    QTextBrowser, QDialog, QListWidget, QListWidgetItem,
    QAbstractItemView, QDialogButtonBox, QFileDialog, QProgressBar,
    QTabWidget
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


# ============= Ollama模型工具调用能力白名单 =============
# 已知支持工具调用的模型家族前缀（不区分大小写）
_TOOL_CAPABLE_PREFIXES = (
    "qwen",
    "llama3.1", "llama3.2", "llama3.3", "llama-3.1", "llama-3.2", "llama-3.3",
    "mistral", "mixtral",
    "command-r",
    "firefunction",
    "nemotron",
    "granite",
    "phi4",
    "deepseek-v2", "deepseek-v3",
    "glm4", "glm-4",
    "internlm",
    "hermes3",
)


def _is_tool_capable(model_name: str) -> bool:
    """检查Ollama模型是否支持工具调用"""
    name = model_name.lower().split(":")[0]
    return any(name.startswith(p.lower()) for p in _TOOL_CAPABLE_PREFIXES)


# ============= LaTeX + Markdown → HTML 渲染 =============

_LATEX_GREEK = {
    r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
    r'\epsilon': 'ε', r'\varepsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η',
    r'\theta': 'θ', r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ',
    r'\mu': 'μ', r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π',
    r'\rho': 'ρ', r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ',
    r'\phi': 'φ', r'\varphi': 'φ', r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
    r'\Gamma': 'Γ', r'\Delta': 'Δ', r'\Theta': 'Θ', r'\Lambda': 'Λ',
    r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ', r'\Phi': 'Φ',
    r'\Psi': 'Ψ', r'\Omega': 'Ω',
}

_LATEX_SYMBOLS = {
    r'\cdot': '·', r'\times': '×', r'\pm': '±', r'\mp': '∓',
    r'\leq': '≤', r'\le': '≤', r'\geq': '≥', r'\ge': '≥',
    r'\neq': '≠', r'\ne': '≠', r'\approx': '≈',
    r'\infty': '∞', r'\partial': '∂', r'\nabla': '∇',
    r'\sum': 'Σ', r'\prod': 'Π', r'\int': '∫',
    r'\rightarrow': '→', r'\leftarrow': '←', r'\Rightarrow': '⇒',
    r'\circ': '°', r'\degree': '°',
}

_LATEX_REMOVE = [r'\displaystyle', r'\left', r'\right', r'\,', r'\;', r'\!', r'\quad', r'\qquad']


def _find_brace_group(text, pos):
    """从pos位置找到匹配的花括号组，返回(start, end)"""
    if pos >= len(text) or text[pos] != '{':
        return None, None
    depth = 0
    for i in range(pos, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return pos, i
    return None, None


def _replace_frac(text):
    """替换第一个 \\frac{num}{den} → (num)/(den)"""
    idx = text.find(r'\frac')
    if idx == -1:
        return text
    pos = idx + len(r'\frac')
    while pos < len(text) and text[pos] == ' ':
        pos += 1
    ns, ne = _find_brace_group(text, pos)
    if ns is None:
        return text.replace(r'\frac', '', 1)
    num = text[ns + 1:ne]
    pos = ne + 1
    while pos < len(text) and text[pos] == ' ':
        pos += 1
    ds, de = _find_brace_group(text, pos)
    if ds is None:
        return text[:idx] + num + text[ne + 1:]
    den = text[ds + 1:de]
    replacement = f'({num})/({den})' if len(num) > 1 or len(den) > 1 else f'{num}/{den}'
    return text[:idx] + replacement + text[de + 1:]


def _convert_latex_math(math_text):
    """将一段 LaTeX 数学公式转为 HTML"""
    t = math_text

    # 移除装饰命令
    for cmd in _LATEX_REMOVE:
        t = t.replace(cmd, '')

    # \ln, \log, \exp 等函数名
    t = re.sub(r'\\(ln|log|exp|sin|cos|tan|lim|max|min)\b', r'\1', t)

    # \text{...} → 内容
    t = re.sub(r'\\text\{([^}]*)\}', r'\1', t)
    # \mathrm{...} → 内容
    t = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', t)

    # \frac{a}{b} → (a)/(b)
    for _ in range(5):  # 最多嵌套5层
        if r'\frac' not in t:
            break
        t = _replace_frac(t)

    # \sqrt{x} → √(x)
    t = re.sub(r'\\sqrt\{([^}]*)\}', r'√(\1)', t)

    # 希腊字母（长名优先，避免部分匹配）
    for cmd in sorted(_LATEX_GREEK.keys(), key=len, reverse=True):
        t = t.replace(cmd, _LATEX_GREEK[cmd])

    # 特殊符号
    for cmd in sorted(_LATEX_SYMBOLS.keys(), key=len, reverse=True):
        t = t.replace(cmd, _LATEX_SYMBOLS[cmd])

    # 下标: _{...} 或 _x
    t = re.sub(r'_\{([^}]*)\}', r'<sub>\1</sub>', t)
    t = re.sub(r'_([a-zA-Z0-9αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ∞°])',
               r'<sub>\1</sub>', t)

    # 上标: ^{...} 或 ^x
    t = re.sub(r'\^\{([^}]*)\}', r'<sup>\1</sup>', t)
    t = re.sub(r'\^([a-zA-Z0-9αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ∞°²³])',
               r'<sup>\1</sup>', t)

    # 清理残留花括号和反斜杠命令
    t = t.replace('{', '').replace('}', '')
    t = re.sub(r'\\[a-zA-Z]+', '', t)  # 移除未识别的 \command

    return t


def _parse_table_row(line):
    """解析表格行，返回单元格内容列表"""
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [cell.strip() for cell in line.split('|')]


def _parse_table_alignments(sep_line):
    """从分隔行解析对齐方式（:--- 左, :---: 居中, ---: 右）"""
    cells = _parse_table_row(sep_line)
    alignments = []
    for cell in cells:
        cell = cell.strip()
        left_colon = cell.startswith(':')
        right_colon = cell.endswith(':')
        if left_colon and right_colon:
            alignments.append('center')
        elif right_colon:
            alignments.append('right')
        else:
            alignments.append('left')
    return alignments


def _convert_markdown_tables(text):
    """将文本中的 Markdown 表格转换为带样式的 HTML <table>"""
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # 检测表格：当前行含 |，下一行是分隔符 |---|
        if ('|' in line and i + 1 < len(lines)
                and re.match(r'^\|?[\s\-:]+(\|[\s\-:]+)+\|?\s*$', lines[i + 1].strip())):
            headers = _parse_table_row(line)
            alignments = _parse_table_alignments(lines[i + 1].strip())
            j = i + 2
            rows = []
            while j < len(lines):
                row_line = lines[j].strip()
                if '|' not in row_line or not row_line:
                    break
                # 跳过额外的分隔行
                if re.match(r'^\|?[\s\-:]+(\|[\s\-:]+)+\|?\s*$', row_line):
                    j += 1
                    continue
                rows.append(_parse_table_row(row_line))
                j += 1

            # 构建 HTML 表格（QTextBrowser 友好的样式）
            table_css = (
                'border-collapse:collapse;margin:10px 0;width:100%;'
                'font-size:15px;border:1px solid #c0c0c0;'
            )
            th_css = (
                'border:1px solid #b0b0b0;padding:9px 16px;'
                'background-color:#4a90d9;color:#ffffff;font-weight:bold;'
            )
            td_css_even = (
                'border:1px solid #d0d0d0;padding:8px 16px;'
                'background-color:#ffffff;'
            )
            td_css_odd = (
                'border:1px solid #d0d0d0;padding:8px 16px;'
                'background-color:#f2f7fc;'
            )

            html = f'<table style="{table_css}">'
            # 表头
            html += '<tr>'
            for idx, h in enumerate(headers):
                align = alignments[idx] if idx < len(alignments) else 'center'
                html += f'<th style="{th_css}text-align:{align};">{h}</th>'
            html += '</tr>'
            # 数据行（斑马条纹）
            for row_idx, row in enumerate(rows):
                td_css = td_css_even if row_idx % 2 == 0 else td_css_odd
                html += '<tr>'
                for idx, cell in enumerate(row):
                    align = alignments[idx] if idx < len(alignments) else 'center'
                    html += f'<td style="{td_css}text-align:{align};">{cell}</td>'
                html += '</tr>'
            html += '</table>'

            result.append(html)
            i = j
        else:
            result.append(lines[i])
            i += 1
    return '\n'.join(result)


def format_message_html(text):
    """将包含 Markdown + LaTeX 的消息文本转换为 QLabel 可渲染的 HTML"""
    if not text:
        return text

    # === 第1步: 处理 LaTeX 数学公式 ===

    # 块级公式: \[ ... \] 或 $$ ... $$
    text = re.sub(
        r'\\\[(.*?)\\\]',
        lambda m: '<div style="text-align:center;margin:6px 0;font-size:17px;">'
                  + _convert_latex_math(m.group(1)) + '</div>',
        text, flags=re.DOTALL)
    text = re.sub(
        r'\$\$(.*?)\$\$',
        lambda m: '<div style="text-align:center;margin:6px 0;font-size:17px;">'
                  + _convert_latex_math(m.group(1)) + '</div>',
        text, flags=re.DOTALL)

    # 行内公式: \( ... \) 或 $ ... $ (单个$不跨行)
    text = re.sub(r'\\\((.*?)\\\)', lambda m: _convert_latex_math(m.group(1)), text)
    text = re.sub(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)',
                  lambda m: _convert_latex_math(m.group(1)), text)

    # 处理散落在文本中的 LaTeX 命令（有些 LLM 不加定界符）
    for cmd in sorted(_LATEX_GREEK.keys(), key=len, reverse=True):
        text = text.replace(cmd, _LATEX_GREEK[cmd])
    for cmd in sorted(_LATEX_SYMBOLS.keys(), key=len, reverse=True):
        text = text.replace(cmd, _LATEX_SYMBOLS[cmd])

    # === 第1.5步: 处理文本中的上下标（非LaTeX环境） ===
    # 先处理花括号形式: X_{abc} → X<sub>abc</sub>, X^{abc} → X<sup>abc</sup>
    text = re.sub(r'_\{([^}]+)\}', r'<sub>\1</sub>', text)
    text = re.sub(r'\^\{([^}]+)\}', r'<sup>\1</sup>', text)
    # 非花括号形式的上下标：支持元素符号（1-2字符如Zn、Mg）、数字序列、希腊字母
    # 不匹配英文单词内的下划线（如 liquidus_temperature）
    _greek = 'αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ'
    _sub_atom = r'[A-Z][a-z]?|[a-z]|[0-9]+|[' + _greek + r']'
    _sup_atom = r'[A-Z][a-z]?|[a-z]|[0-9]+|[' + _greek + r'²³⁰¹⁴⁵⁶⁷⁸⁹]'
    # 希腊字母或闭标签 + _x / ^x（如 ε_Zn, γ_Zn, ε_Zn^Mg）
    text = re.sub(
        r'(?<=[' + _greek + r'>])_(' + _sub_atom + r')',
        r'<sub>\1</sub>', text)
    text = re.sub(
        r'(?<=[' + _greek + r'>])\^(' + _sup_atom + r')',
        r'<sup>\1</sup>', text)
    # 单字母变量 + _x / ^x（仅当该单字母前面不是字母时，排除 word_word 情况）
    text = re.sub(
        r'(?<![a-zA-Z])([a-zA-Z])_(' + _sub_atom + r')',
        r'\1<sub>\2</sub>', text)
    text = re.sub(
        r'(?<![a-zA-Z])([a-zA-Z])\^(' + _sup_atom + r')',
        r'\1<sup>\2</sup>', text)

    # === 第2步: 处理 Markdown 表格（需在换行转换前完成） ===
    text = _convert_markdown_tables(text)

    # === 第3步: 处理其他 Markdown ===

    # 标题
    text = re.sub(r'^#### (.+)$', r'<h5>\1</h5>', text, flags=re.MULTILINE)
    text = re.sub(r'^### (.+)$', r'<h4>\1</h4>', text, flags=re.MULTILINE)
    text = re.sub(r'^## (.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
    text = re.sub(r'^# (.+)$', r'<h2>\1</h2>', text, flags=re.MULTILINE)

    # 加粗（先于斜体）
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)

    # 行内代码
    text = re.sub(r'`([^`]+)`', r'<code style="background:#e8e8e8;padding:1px 4px;border-radius:3px;">\1</code>', text)

    # 无序列表
    text = re.sub(r'^[-*] (.+)$', r'&nbsp;&nbsp;• \1', text, flags=re.MULTILINE)

    # 有序列表
    text = re.sub(r'^(\d+)\. (.+)$', r'&nbsp;&nbsp;\1. \2', text, flags=re.MULTILINE)

    # 分隔线
    text = re.sub(r'^---+$', '<hr>', text, flags=re.MULTILINE)

    # 换行
    text = text.replace('\n', '<br>')

    return text


class ChatWorker(QThread):
    """后台对话处理线程"""
    response_ready = pyqtSignal(str)
    tool_called = pyqtSignal(str, dict)
    tool_result_ready = pyqtSignal(str, str)  # (tool_name, result_json)
    chart_requested = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, agent, message: str):
        super().__init__()
        self.agent = agent
        self.message = message

    def run(self):
        try:
            # 设置工具调用回调，检测图表工具
            original_call_cb = self.agent.on_tool_call
            original_result_cb = self.agent.on_tool_result

            def _on_tool(name, args):
                self.tool_called.emit(name, args)
                if name == "plot_chart":
                    self.chart_requested.emit(args)

            def _on_result(name, result):
                self.tool_result_ready.emit(name, result)

            self.agent.on_tool_call = _on_tool
            self.agent.on_tool_result = _on_result

            response = self.agent.chat(self.message)
            self.response_ready.emit(response)

            # 恢复原始回调
            self.agent.on_tool_call = original_call_cb
            self.agent.on_tool_result = original_result_cb
        except Exception as e:
            self.error_occurred.emit(str(e))


class _OllamaModelWorker(QThread):
    """后台线程：获取Ollama模型列表，避免阻塞UI"""
    finished_signal = pyqtSignal(list)

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url

    def run(self):
        import urllib.request
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                self.finished_signal.emit(sorted(models) if models else [])
        except Exception:
            self.finished_signal.emit([])


# 右键菜单样式（浅色主题，与气泡风格统一）
_CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: #ffffff;
        border: 1px solid #c0c0c0;
        border-radius: 6px;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 6px 28px 6px 12px;
        color: #2c3e50;
        font-size: 13px;
    }
    QMenu::item:selected {
        background-color: #e8f4f8;
        color: #1a5276;
    }
    QMenu::item:disabled {
        color: #aaaaaa;
    }
    QMenu::separator {
        height: 1px;
        background: #e0e0e0;
        margin: 3px 8px;
    }
"""


class StyledTextBrowser(QTextBrowser):
    """支持浅色右键菜单的 QTextBrowser"""

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.setStyleSheet(_CONTEXT_MENU_STYLE)
        menu.exec_(event.globalPos())
        menu.deleteLater()


class MessageBubble(QFrame):
    """消息气泡组件"""

    def __init__(self, text: str, is_user: bool = True, parent=None):
        super().__init__(parent)
        self.setup_ui(text, is_user)

    def setup_ui(self, text: str, is_user: bool):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # 角色标签
        role_label = QLabel("你" if is_user else "助手")
        role_label.setStyleSheet(f"""
            font-weight: bold;
            color: {'#2c3e50' if is_user else '#27ae60'};
            font-size: 13px;
        """)

        # 消息内容（助手消息使用QTextBrowser渲染，支持完整HTML表格；用户消息保持QLabel）
        if is_user:
            content_label = QLabel()
            content_label.setText(text)
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
            )
            content_label.setContextMenuPolicy(Qt.CustomContextMenu)
            content_label.customContextMenuRequested.connect(
                lambda pos, lbl=content_label: self._show_label_context_menu(lbl, pos)
            )
            content_label.setStyleSheet("""
                background: transparent;
                font-size: 18px;
                padding: 5px;
            """)
        else:
            content_label = StyledTextBrowser()
            content_label.setOpenExternalLinks(False)
            content_label.setHtml(format_message_html(text))
            content_label.setStyleSheet("""
                QTextBrowser {
                    background: transparent;
                    font-size: 18px;
                    padding: 5px;
                    border: none;
                }
            """)
            # 根据内容自动调整高度：监听documentSizeChanged（布局完成后触发，宽度已确定）
            content_label.document().setDocumentMargin(4)
            content_label.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            content_label.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            content_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            content_label.setFixedHeight(20)  # 初始占位，布局后会自动调整

            def _adjust_height(size, browser=content_label):
                browser.setFixedHeight(int(size.height()) + 12)

            content_label.document().documentLayout().documentSizeChanged.connect(
                _adjust_height
            )

        layout.addWidget(role_label)
        layout.addWidget(content_label)

        # 气泡样式
        if is_user:
            bg, border = "#dceefb", "#c4ddf0"
        else:
            bg, border = "#ffffff", "#e2e2e2"
        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {bg};
                border: 1px solid {border};
                border-radius: 10px;
                margin: 2px 4px;
            }}
        """)

    @staticmethod
    def _show_label_context_menu(label: QLabel, pos):
        """为 QLabel 显示浅色风格的右键菜单"""
        from PyQt5.QtWidgets import QMenu, QApplication
        menu = QMenu(label)
        menu.setStyleSheet(_CONTEXT_MENU_STYLE)

        copy_action = menu.addAction("复制")
        copy_action.setEnabled(label.hasSelectedText())
        select_all_action = menu.addAction("全选")

        action = menu.exec_(label.mapToGlobal(pos))
        if action == copy_action:
            QApplication.clipboard().setText(label.selectedText())
        elif action == select_all_action:
            # QLabel 没有 selectAll()，通过 setSelection 实现
            cursor = label.cursorForPosition(pos)
            label.setSelection(0, len(label.text()))
        menu.deleteLater()


class ToolCallBubble(QFrame):
    """工具调用气泡组件"""

    def __init__(self, tool_name: str, arguments: dict, parent=None):
        super().__init__(parent)
        self.setup_ui(tool_name, arguments)

    def setup_ui(self, tool_name: str, arguments: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # 标题
        title_label = QLabel(f"调用: {tool_name}")
        title_label.setStyleSheet("""
            font-weight: bold;
            color: #8e44ad;
            font-size: 12px;
        """)

        # 参数（简化显示）
        args_text = json.dumps(arguments, ensure_ascii=False, indent=2)
        if len(args_text) > 200:
            args_text = args_text[:200] + "..."
        args_label = QLabel(args_text)
        args_label.setWordWrap(True)
        args_label.setStyleSheet("""
            font-family: Consolas, Monaco, monospace;
            font-size: 11px;
            color: #555;
            padding: 5px;
        """)

        layout.addWidget(title_label)
        layout.addWidget(args_label)

        self.setStyleSheet("""
            ToolCallBubble {
                background-color: #f8f0ff;
                border: 1px solid #d8c0e8;
                border-radius: 8px;
                margin: 3px 20px;
            }
        """)


class ToolResultBubble(QFrame):
    """工具执行结果气泡组件"""

    def __init__(self, tool_name: str, result_json: str, parent=None):
        super().__init__(parent)
        self.setup_ui(tool_name, result_json)

    def setup_ui(self, tool_name: str, result_json: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # 解析结果
        try:
            data = json.loads(result_json) if isinstance(result_json, str) else result_json
        except (json.JSONDecodeError, TypeError):
            data = {"result": result_json}

        is_error = isinstance(data, dict) and data.get("status") == "error"

        # 标题
        status_icon = "x" if is_error else "="
        title_label = QLabel(f"  {status_icon} 结果: {tool_name}")
        title_label.setStyleSheet(f"""
            font-weight: bold;
            color: {'#e74c3c' if is_error else '#27ae60'};
            font-size: 12px;
        """)

        # 结果内容（格式化关键数值）
        if is_error:
            result_text = data.get("message", str(data))
        elif isinstance(data, dict):
            lines = []
            for key, value in data.items():
                if key in ("status", "iterations"):
                    continue
                if isinstance(value, float):
                    lines.append(f"{key}: {value:.6g}")
                elif isinstance(value, (int, str, bool)):
                    lines.append(f"{key}: {value}")
                elif isinstance(value, dict):
                    lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
            result_text = "\n".join(lines) if lines else json.dumps(data, ensure_ascii=False, indent=2)
        else:
            result_text = str(data)

        if len(result_text) > 500:
            result_text = result_text[:500] + "\n..."

        result_label = QLabel(result_text)
        result_label.setWordWrap(True)
        result_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        result_label.setStyleSheet("""
            font-family: Consolas, Monaco, monospace;
            font-size: 11px;
            color: #333;
            padding: 5px;
        """)

        layout.addWidget(title_label)
        layout.addWidget(result_label)

        bg_color = "#fff0f0" if is_error else "#f0fff0"
        border_color = "#e8c0c0" if is_error else "#c0e8c0"
        self.setStyleSheet(f"""
            ToolResultBubble {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                margin: 0px 20px 3px 20px;
            }}
        """)


class ChartBubble(QFrame):
    """图表气泡组件 - 在对话中嵌入matplotlib图表"""

    def __init__(self, chart_data: dict, parent=None):
        super().__init__(parent)
        self.setup_ui(chart_data)

    def setup_ui(self, chart_data: dict):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)

        # 创建matplotlib画布
        fig = Figure(figsize=(6, 4), dpi=100)
        fig.patch.set_facecolor('#ffffff')
        ax = fig.add_subplot(111)

        chart_type = chart_data.get("chart_type", "line")
        data_series = chart_data.get("data_series", [])

        # 绘制数据
        colors = ['#2980b9', '#e74c3c', '#27ae60', '#f39c12', '#8e44ad',
                  '#1abc9c', '#d35400', '#2c3e50']
        for i, series in enumerate(data_series):
            x = series.get("x_values", [])
            y = series.get("y_values", [])
            name = series.get("name", f"Series {i+1}")
            color = colors[i % len(colors)]

            if chart_type == "scatter":
                ax.scatter(x, y, label=name, color=color, s=30, alpha=0.8)
            elif chart_type == "bar":
                import numpy as np
                width = 0.8 / max(len(data_series), 1)
                offset = (i - len(data_series) / 2 + 0.5) * width
                ax.bar([xi + offset for xi in range(len(x))], y,
                       width=width, label=name, color=color, alpha=0.8)
                if len(x) > 0:
                    ax.set_xticks(range(len(x)))
                    ax.set_xticklabels([str(xi) for xi in x], rotation=45, ha='right')
            else:  # line
                ax.plot(x, y, label=name, color=color, linewidth=2, marker='o',
                        markersize=4, alpha=0.9)

        ax.set_title(chart_data.get("title", ""), fontsize=13, fontweight='bold', pad=10)
        ax.set_xlabel(chart_data.get("x_label", ""), fontsize=11)
        ax.set_ylabel(chart_data.get("y_label", ""), fontsize=11)

        if len(data_series) > 1:
            ax.legend(fontsize=9, loc='best')

        ax.grid(True, alpha=0.3, linestyle='--')
        fig.tight_layout()

        canvas = FigureCanvas(fig)
        canvas.setMinimumHeight(320)
        canvas.setMaximumHeight(450)
        layout.addWidget(canvas)

        self.setStyleSheet("""
            ChartBubble {
                background-color: #ffffff;
                border: 1px solid #c8e6c8;
                border-radius: 10px;
                margin: 5px;
            }
        """)


class MemoryDialog(QDialog):
    """记忆管理对话框 — 查看、添加、删除AI助手的持久记忆"""

    # 分类中文映射
    _CATEGORIES = {
        "preference": "计算偏好",
        "alloy_system": "常用合金体系",
        "calculation": "计算规则",
        "general": "其他",
    }

    def __init__(self, memory_store, parent=None):
        super().__init__(parent)
        self.memory_store = memory_store
        self.setWindowTitle("AI 记忆管理")
        self.setMinimumSize(560, 420)
        self._setup_ui()
        self._refresh_list()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # 说明
        hint = QLabel("AI助手会根据对话自动记住您的计算偏好。您也可以在此手动管理。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#666;font-size:12px;margin-bottom:6px;")
        layout.addWidget(hint)

        # 记忆列表
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #d5e8f6;
                color: #000;
            }
        """)
        layout.addWidget(self.list_widget, stretch=1)

        # 手动添加区域
        add_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("输入要记住的内容，如：默认使用Elliott活度模型")
        add_layout.addWidget(self.input_edit, stretch=1)

        self.category_combo = QComboBox()
        for key, label in self._CATEGORIES.items():
            self.category_combo.addItem(label, key)
        self.category_combo.setMinimumWidth(100)
        add_layout.addWidget(self.category_combo)

        add_btn = QPushButton("添加")
        add_btn.clicked.connect(self._add_memory)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #219a52; }
        """)
        add_layout.addWidget(add_btn)
        layout.addLayout(add_layout)

        # 底部按钮
        btn_layout = QHBoxLayout()

        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._delete_selected)
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #c0392b; }
        """)
        btn_layout.addWidget(del_btn)

        clear_btn = QPushButton("清除全部")
        clear_btn.clicked.connect(self._clear_all)
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6; color: white;
                padding: 6px 16px; border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        btn_layout.addWidget(clear_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db; color: white;
                padding: 6px 20px; border: none; border-radius: 4px;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def _refresh_list(self):
        """刷新记忆列表"""
        self.list_widget.clear()
        for mem in self.memory_store.get_all():
            cat_label = self._CATEGORIES.get(mem.category, mem.category)
            item = QListWidgetItem(f"[{cat_label}]  {mem.content}")
            item.setData(Qt.UserRole, mem.content)
            self.list_widget.addItem(item)

    def _add_memory(self):
        """手动添加记忆"""
        content = self.input_edit.text().strip()
        if not content:
            return
        category = self.category_combo.currentData()
        self.memory_store.add(content, category, source="用户手动添加")
        self.input_edit.clear()
        self._refresh_list()

    def _delete_selected(self):
        """删除选中的记忆"""
        selected = self.list_widget.selectedItems()
        if not selected:
            return
        for item in selected:
            content = item.data(Qt.UserRole)
            self.memory_store.remove(content)
        self._refresh_list()

    def _clear_all(self):
        """清除所有记忆"""
        reply = QMessageBox.question(
            self, "确认", "确定要清除所有记忆吗？此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.memory_store.clear_all()
            self._refresh_list()


class DocumentImportWorker(QThread):
    """文档导入后台线程"""
    progress = pyqtSignal(int, int, str)  # (current, total, message)
    finished = pyqtSignal(dict)            # result dict

    def __init__(self, filepath, knowledge_store, category, confidence,
                 llm_config: dict = None):
        super().__init__()
        self.filepath = filepath
        self.knowledge_store = knowledge_store
        self.category = category
        self.confidence = confidence
        self.llm_config = llm_config

    def run(self):
        from llm.document_learner import import_document
        # 创建AI视觉识别器（如果已配置LLM）
        vision = None
        if self.llm_config:
            try:
                from llm.vision_recognition import VisionRecognizer
                vision = VisionRecognizer(**self.llm_config)
            except Exception:
                pass
        result = import_document(
            filepath=self.filepath,
            knowledge_store=self.knowledge_store,
            category=self.category,
            confidence=self.confidence,
            progress_callback=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
            vision_recognizer=vision
        )
        self.finished.emit(result)


class KnowledgeDialog(QDialog):
    """知识库管理对话框 — 查看AI学到的领域知识和用户提供的实验数据"""

    _K_CATEGORIES = {
        "theory": "理论知识",
        "formula": "公式模型",
        "experimental": "实验规律",
        "experience": "计算经验",
        "correction": "数据修正",
        "general": "其他",
    }

    def __init__(self, knowledge_store, llm_config: dict = None,
                 skill_registry=None, parent=None):
        super().__init__(parent)
        self.knowledge_store = knowledge_store
        self.llm_config = llm_config  # LLM配置，用于AI视觉识别
        self.skill_registry = skill_registry
        self._import_worker = None
        self._knowledge_entries = []
        self._data_entries = []
        self.setWindowTitle("知识库管理")
        self.setMinimumSize(780, 520)
        # 自适应屏幕尺寸
        try:
            from PyQt5.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().availableGeometry()
            w = min(960, int(screen.width() * 0.62))
            h = min(720, int(screen.height() * 0.72))
            self.resize(w, h)
        except Exception:
            self.resize(900, 660)
        self._setup_ui()
        self._refresh_all()

    # ==================== UI 布局 ====================

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # 标题
        title = QLabel("知识库管理")
        title.setStyleSheet(
            "font-size:18px; font-weight:bold; color:#2c3e50; margin-bottom:2px;"
        )
        layout.addWidget(title)

        # 说明
        hint = QLabel(
            "AI助手通过对话不断学习领域知识，并保存用户提供的实验数据。"
            "您也可以导入教材/文献 PDF（含表格与图片识别），让AI从书本中学习。"
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#7f8c8d; font-size:12px; margin-bottom:4px;")
        layout.addWidget(hint)

        # 统计栏
        stats_bar = QHBoxLayout()
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(
            "font-size:13px; color:#2c3e50; font-weight:bold;"
        )
        stats_bar.addWidget(self.stats_label, stretch=1)
        layout.addLayout(stats_bar)

        # 文档上传 + 学习栏
        import_bar = QHBoxLayout()
        import_bar.setSpacing(8)

        self.import_btn = QPushButton("上传文档")
        self.import_btn.setToolTip("选择 PDF / TXT 教材或文献")
        self.import_btn.clicked.connect(self._select_document)
        self.import_btn.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white;
                          padding:5px 14px; border:none; border-radius:5px;
                          font-size:13px; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        import_bar.addWidget(self.import_btn)

        self.file_label = QLabel("未选择文件")
        self.file_label.setStyleSheet(
            "color:#999; font-size:12px; padding:0 4px;"
        )
        self.file_label.setWordWrap(False)
        import_bar.addWidget(self.file_label, stretch=1)

        import_bar.addWidget(QLabel("分类:"))
        self.import_category_combo = QComboBox()
        for key, label in self._K_CATEGORIES.items():
            self.import_category_combo.addItem(label, key)
        self.import_category_combo.setCurrentIndex(0)
        self.import_category_combo.setMinimumWidth(90)
        self.import_category_combo.setStyleSheet(
            "QComboBox { padding:3px 6px; border:1px solid #ccc; border-radius:4px; }"
        )
        import_bar.addWidget(self.import_category_combo)

        self.learn_btn = QPushButton("学习")
        self.learn_btn.setToolTip("开始从上传的文档中学习知识（含表格和图片AI识别）")
        self.learn_btn.setEnabled(False)
        self.learn_btn.clicked.connect(self._start_learning)
        self.learn_btn.setStyleSheet("""
            QPushButton { background-color:#2ecc71; color:white;
                          padding:5px 16px; border:none; border-radius:5px;
                          font-weight:bold; font-size:13px; }
            QPushButton:hover { background-color:#27ae60; }
            QPushButton:disabled { background-color:#bdc3c7; color:#fff; }
        """)
        import_bar.addWidget(self.learn_btn)

        layout.addLayout(import_bar)

        # 进度条（默认隐藏）
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { border:1px solid #ccc; border-radius:6px; height:22px;
                           text-align:center; font-size:11px; background:#f0f0f0; }
            QProgressBar::chunk { background-color:#2ecc71; border-radius:5px; }
        """)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel()
        self.progress_label.setStyleSheet("font-size:11px; color:#666;")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # ---- 选项卡 ----
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border:1px solid #ddd; border-radius:6px; background:white;
            }
            QTabBar::tab {
                padding:8px 24px; margin-right:2px;
                border:1px solid #ddd; border-bottom:none;
                border-top-left-radius:6px; border-top-right-radius:6px;
                background:#f5f5f5; color:#555; font-size:13px;
            }
            QTabBar::tab:selected {
                background:white; color:#2c3e50; font-weight:bold;
                border-bottom:2px solid white; margin-bottom:-1px;
            }
            QTabBar::tab:hover:!selected { background:#e8e8e8; }
        """)

        # ===== Tab 1: 领域知识 =====
        k_tab = QWidget()
        k_layout = QVBoxLayout(k_tab)
        k_layout.setContentsMargins(8, 8, 8, 8)
        k_layout.setSpacing(6)

        k_splitter = QSplitter(Qt.Vertical)
        self.knowledge_list = QListWidget()
        self.knowledge_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.knowledge_list.setWordWrap(True)
        self.knowledge_list.currentRowChanged.connect(self._on_knowledge_selected)
        self.knowledge_list.setStyleSheet("""
            QListWidget {
                border:1px solid #e0e0e0; border-radius:6px;
                font-size:13px; background:white; outline:none;
            }
            QListWidget::item {
                padding:8px 12px; border-bottom:1px solid #f0f0f0;
            }
            QListWidget::item:selected { background-color:#d5e8f6; color:#000; }
            QListWidget::item:hover:!selected { background-color:#f5f9ff; }
        """)
        k_splitter.addWidget(self.knowledge_list)

        self.knowledge_detail = QTextBrowser()
        self.knowledge_detail.setOpenExternalLinks(False)
        self.knowledge_detail.setStyleSheet("""
            QTextBrowser {
                border:1px solid #e0e0e0; border-radius:6px;
                padding:10px; font-size:13px; background:#fafbfc;
            }
        """)
        k_splitter.addWidget(self.knowledge_detail)
        k_splitter.setStretchFactor(0, 3)
        k_splitter.setStretchFactor(1, 2)
        k_layout.addWidget(k_splitter, stretch=1)

        k_btn_bar = QHBoxLayout()
        k_btn_bar.setSpacing(8)

        del_k_btn = QPushButton("删除选中知识")
        del_k_btn.clicked.connect(self._delete_knowledge)
        del_k_btn.setStyleSheet("""
            QPushButton { background-color:#e74c3c; color:white;
                          padding:5px 14px; border:none; border-radius:5px;
                          font-size:12px; }
            QPushButton:hover { background-color:#c0392b; }
        """)
        k_btn_bar.addWidget(del_k_btn)

        optimize_btn = QPushButton("优化知识库")
        optimize_btn.setToolTip("自动检测相似条目并合并去重")
        optimize_btn.clicked.connect(self._optimize_knowledge)
        optimize_btn.setStyleSheet("""
            QPushButton { background-color:#2ecc71; color:white;
                          padding:5px 14px; border:none; border-radius:5px;
                          font-size:12px; font-weight:bold; }
            QPushButton:hover { background-color:#27ae60; }
        """)
        k_btn_bar.addWidget(optimize_btn)
        k_btn_bar.addStretch()

        k_layout.addLayout(k_btn_bar)

        self.tab_widget.addTab(k_tab, "领域知识")

        # ===== Tab 2: 实验数据 =====
        d_tab = QWidget()
        d_layout = QVBoxLayout(d_tab)
        d_layout.setContentsMargins(8, 8, 8, 8)
        d_layout.setSpacing(6)

        d_splitter = QSplitter(Qt.Vertical)
        self.data_list = QListWidget()
        self.data_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.data_list.setWordWrap(True)
        self.data_list.currentRowChanged.connect(self._on_data_selected)
        self.data_list.setStyleSheet("""
            QListWidget {
                border:1px solid #e0e0e0; border-radius:6px;
                font-size:13px; background:white; outline:none;
            }
            QListWidget::item {
                padding:8px 12px; border-bottom:1px solid #f0f0f0;
            }
            QListWidget::item:selected { background-color:#fde8e8; color:#000; }
            QListWidget::item:hover:!selected { background-color:#fff8f8; }
        """)
        d_splitter.addWidget(self.data_list)

        self.data_detail = QTextBrowser()
        self.data_detail.setOpenExternalLinks(False)
        self.data_detail.setStyleSheet("""
            QTextBrowser {
                border:1px solid #e0e0e0; border-radius:6px;
                padding:10px; font-size:13px; background:#fafbfc;
            }
        """)
        d_splitter.addWidget(self.data_detail)
        d_splitter.setStretchFactor(0, 3)
        d_splitter.setStretchFactor(1, 2)
        d_layout.addWidget(d_splitter, stretch=1)

        del_d_btn = QPushButton("删除选中数据")
        del_d_btn.clicked.connect(self._delete_data)
        del_d_btn.setStyleSheet("""
            QPushButton { background-color:#e67e22; color:white;
                          padding:5px 14px; border:none; border-radius:5px;
                          font-size:12px; }
            QPushButton:hover { background-color:#d35400; }
        """)
        d_layout.addWidget(del_d_btn, alignment=Qt.AlignLeft)

        self.tab_widget.addTab(d_tab, "实验数据")

        # ===== Tab 3: 自定义技能 =====
        s_tab = QWidget()
        s_layout = QVBoxLayout(s_tab)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(6)

        s_hint = QLabel(
            "通过对话让AI创建自定义计算工具。例如告诉AI：'帮我加一个计算理想混合熵的功能'。"
            "技能保存在本地，重启后仍可使用。"
        )
        s_hint.setWordWrap(True)
        s_hint.setStyleSheet("color:#7f8c8d; font-size:12px; margin-bottom:4px;")
        s_layout.addWidget(s_hint)

        s_splitter = QSplitter(Qt.Vertical)
        self.skill_list = QListWidget()
        self.skill_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.skill_list.setWordWrap(True)
        self.skill_list.currentRowChanged.connect(self._on_skill_selected)
        self.skill_list.setStyleSheet("""
            QListWidget {
                border:1px solid #e0e0e0; border-radius:6px;
                font-size:13px; background:white; outline:none;
            }
            QListWidget::item {
                padding:8px 12px; border-bottom:1px solid #f0f0f0;
            }
            QListWidget::item:selected { background-color:#e8d5f6; color:#000; }
            QListWidget::item:hover:!selected { background-color:#f9f5ff; }
        """)
        s_splitter.addWidget(self.skill_list)

        self.skill_detail = QTextBrowser()
        self.skill_detail.setOpenExternalLinks(False)
        self.skill_detail.setStyleSheet("""
            QTextBrowser {
                border:1px solid #e0e0e0; border-radius:6px;
                padding:10px; font-size:13px; background:#fafbfc;
                font-family: 'Consolas', 'Courier New', monospace;
            }
        """)
        s_splitter.addWidget(self.skill_detail)
        s_splitter.setStretchFactor(0, 2)
        s_splitter.setStretchFactor(1, 3)
        s_layout.addWidget(s_splitter, stretch=1)

        del_s_btn = QPushButton("删除选中技能")
        del_s_btn.clicked.connect(self._delete_skill)
        del_s_btn.setStyleSheet("""
            QPushButton { background-color:#8e44ad; color:white;
                          padding:5px 14px; border:none; border-radius:5px;
                          font-size:12px; }
            QPushButton:hover { background-color:#7d3c98; }
        """)
        s_layout.addWidget(del_s_btn, alignment=Qt.AlignLeft)

        self.tab_widget.addTab(s_tab, "自定义技能")

        layout.addWidget(self.tab_widget, stretch=1)

        # 底部关闭按钮
        btn_bar = QHBoxLayout()
        btn_bar.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white;
                          padding:7px 28px; border:none; border-radius:6px;
                          font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_bar.addWidget(close_btn)
        layout.addLayout(btn_bar)

    # ==================== 数据刷新 ====================

    def _refresh_all(self):
        """刷新所有列表"""
        stats = self.knowledge_store.get_stats()
        skill_count = 0
        if self.skill_registry:
            skill_count = self.skill_registry.get_skill_count()
        self.stats_label.setText(
            f"知识条目: {stats['knowledge_count']}   |   "
            f"实验数据: {stats['user_data_count']}   |   "
            f"自定义技能: {skill_count}"
        )

        # 知识列表
        self._knowledge_entries = list(self.knowledge_store.get_all_knowledge())
        self.knowledge_list.clear()
        self.knowledge_detail.clear()
        for entry in self._knowledge_entries:
            cat = self._K_CATEGORIES.get(entry.category, entry.category)
            text = f"[{cat}]  {entry.topic}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry.id)
            self.knowledge_list.addItem(item)

        # 实验数据列表
        self._data_entries = list(self.knowledge_store.get_all_user_data())
        self.data_list.clear()
        self.data_detail.clear()
        for entry in self._data_entries:
            text = (f"{entry.solvent}中 {entry.value_type}"
                    f"({entry.solute_i}"
                    f"{', ' + entry.solute_j if entry.solute_j else ''}) = "
                    f"{entry.value}   T={entry.temperature}K   "
                    f"[{entry.reference}]")
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry.id)
            self.data_list.addItem(item)

        # 技能列表
        self.skill_list.clear()
        self.skill_detail.clear()
        if self.skill_registry:
            for skill in self.skill_registry.list_skills():
                status = "启用" if skill["enabled"] else "禁用"
                text = f"[{status}]  {skill['name']}  —  {skill['description']}"
                item = QListWidgetItem(text)
                item.setData(Qt.UserRole, skill["name"])
                self.skill_list.addItem(item)

    # ==================== 详情面板 ====================

    def _on_knowledge_selected(self, row: int):
        """知识条目选中时显示详情"""
        if row < 0 or row >= len(self._knowledge_entries):
            self.knowledge_detail.clear()
            return
        entry = self._knowledge_entries[row]
        cat = self._K_CATEGORIES.get(entry.category, entry.category)
        html = (
            f"<div style='margin-bottom:8px;'>"
            f"<span style='background:#3498db;color:white;padding:2px 8px;"
            f"border-radius:3px;font-size:12px;'>{cat}</span>"
            f"<span style='color:#999;font-size:12px;margin-left:10px;'>"
            f"置信度: {entry.confidence:.0%}</span>"
            f"</div>"
            f"<div style='font-weight:bold;font-size:14px;color:#2c3e50;"
            f"margin-bottom:6px;'>{entry.topic}</div>"
            f"<div style='font-size:12px;color:#888;margin-bottom:8px;'>"
            f"来源: {entry.source}"
        )
        if entry.tags:
            html += f" &nbsp;|&nbsp; 标签: {entry.tags}"
        html += "</div><hr style='border:none;border-top:1px solid #eee;'>"
        content = entry.content.replace('\n', '<br>')
        html += (
            f"<div style='font-size:13px;line-height:1.6;color:#333;'>"
            f"{content}</div>"
        )
        self.knowledge_detail.setHtml(html)

    def _on_data_selected(self, row: int):
        """实验数据选中时显示详情"""
        if row < 0 or row >= len(self._data_entries):
            self.data_detail.clear()
            return
        entry = self._data_entries[row]
        html = (
            "<table style='font-size:13px;color:#333;border-collapse:collapse;"
            "width:100%;'>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;width:100px;'>"
            f"溶剂</td><td style='padding:4px 8px;'>{entry.solvent}</td></tr>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>溶质 i</td>"
            f"<td style='padding:4px 8px;'>{entry.solute_i}</td></tr>"
        )
        if entry.solute_j:
            html += (
                f"<tr><td style='padding:4px 8px;font-weight:bold;'>溶质 j</td>"
                f"<td style='padding:4px 8px;'>{entry.solute_j}</td></tr>"
            )
        html += (
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>数据类型</td>"
            f"<td style='padding:4px 8px;'>{entry.data_type}</td></tr>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>值类型</td>"
            f"<td style='padding:4px 8px;'>{entry.value_type}</td></tr>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>数值</td>"
            f"<td style='padding:4px 8px;font-weight:bold;color:#e74c3c;'>"
            f"{entry.value}</td></tr>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>温度</td>"
            f"<td style='padding:4px 8px;'>{entry.temperature} K</td></tr>"
            f"<tr><td style='padding:4px 8px;font-weight:bold;'>文献来源</td>"
            f"<td style='padding:4px 8px;'>{entry.reference}</td></tr>"
        )
        if entry.note:
            html += (
                f"<tr><td style='padding:4px 8px;font-weight:bold;'>备注</td>"
                f"<td style='padding:4px 8px;'>{entry.note}</td></tr>"
            )
        html += "</table>"
        self.data_detail.setHtml(html)

    # ==================== 删除操作 ====================

    def _delete_knowledge(self):
        """删除选中的知识"""
        selected = self.knowledge_list.selectedItems()
        if not selected:
            return
        for item in selected:
            kid = item.data(Qt.UserRole)
            self.knowledge_store.delete_knowledge(kid)
        self._refresh_all()

    def _optimize_knowledge(self):
        """优化知识库：检测相似条目并合并去重"""
        all_entries = self.knowledge_store.get_all_knowledge()
        if len(all_entries) < 2:
            QMessageBox.information(self, "提示", "知识库条目不足，无需优化。")
            return

        # 查找相似组
        processed = set()
        merge_groups = []
        for entry in all_entries:
            if entry.id in processed:
                continue
            similar = self.knowledge_store.find_similar_knowledge(
                entry.topic, entry.content, threshold=0.6
            )
            group_ids = [entry.id]
            group_entries = [entry]
            for sim_entry, sim_score in similar:
                if sim_entry.id != entry.id and sim_entry.id not in processed:
                    group_ids.append(sim_entry.id)
                    group_entries.append(sim_entry)
                    processed.add(sim_entry.id)
            if len(group_ids) > 1:
                processed.add(entry.id)
                merge_groups.append((group_ids, group_entries))

        if not merge_groups:
            QMessageBox.information(self, "优化结果", "未发现需要合并的相似知识。")
            return

        # 展示发现的相似组，让用户确认
        detail_lines = []
        for i, (group_ids, group_entries) in enumerate(merge_groups, 1):
            topics = [e.topic for e in group_entries]
            detail_lines.append(f"第{i}组 ({len(group_ids)}条): {' | '.join(topics)}")

        reply = QMessageBox.question(
            self, "确认合并",
            f"发现 {len(merge_groups)} 组相似知识：\n\n"
            + "\n".join(detail_lines[:10])
            + ("\n..." if len(detail_lines) > 10 else "")
            + "\n\n每组将合并为一条（保留最高置信度和最长内容）。确定执行？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        # 执行合并
        total_merged = 0
        for group_ids, group_entries in merge_groups:
            best = max(group_entries, key=lambda e: (e.confidence, e.access_count))
            longest = max(group_entries, key=lambda e: len(e.content))
            self.knowledge_store.merge_knowledge(
                source_ids=group_ids,
                merged_topic=best.topic,
                merged_content=longest.content,
                category=best.category,
                confidence=best.confidence
            )
            total_merged += len(group_ids)

        self._refresh_all()
        QMessageBox.information(
            self, "优化完成",
            f"知识库优化完成！\n\n"
            f"合并了 {len(merge_groups)} 组共 {total_merged} 条知识。"
        )

    def _delete_data(self):
        """删除选中的实验数据"""
        selected = self.data_list.selectedItems()
        if not selected:
            return
        reply = QMessageBox.question(
            self, "确认", "删除后该数据将不再覆盖默认数据库值。确定删除？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for item in selected:
                did = item.data(Qt.UserRole)
                self.knowledge_store.delete_user_data(did)
            self._refresh_all()

    # ==================== 技能管理 ====================

    def _on_skill_selected(self, row: int):
        """技能选中时显示详情（代码）"""
        if not self.skill_registry:
            self.skill_detail.clear()
            return
        skills = self.skill_registry.list_skills()
        if row < 0 or row >= len(skills):
            self.skill_detail.clear()
            return
        skill = skills[row]
        # 从 registry 取完整信息（含 code）
        full = self.skill_registry._skills.get(skill["name"])
        if not full:
            return
        import time as _time
        created = _time.strftime(
            "%Y-%m-%d %H:%M", _time.localtime(full.created_at)
        )
        tags_str = ", ".join(full.tags) if full.tags else "无"
        code_html = full.code.replace("&", "&amp;").replace(
            "<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
        html = (
            f"<div style='margin-bottom:6px;'>"
            f"<span style='background:#8e44ad;color:white;padding:2px 8px;"
            f"border-radius:3px;font-size:12px;'>技能</span>"
            f"<span style='color:#999;font-size:12px;margin-left:10px;'>"
            f"创建: {created} &nbsp;|&nbsp; 版本: v{full.version}</span></div>"
            f"<div style='font-weight:bold;font-size:14px;color:#2c3e50;"
            f"margin-bottom:4px;'>{full.name}</div>"
            f"<div style='font-size:12px;color:#666;margin-bottom:4px;'>"
            f"{full.description}</div>"
            f"<div style='font-size:12px;color:#888;margin-bottom:8px;'>"
            f"标签: {tags_str}</div>"
            f"<hr style='border:none;border-top:1px solid #eee;'>"
            f"<div style='font-size:12px;font-family:Consolas,monospace;"
            f"background:#f8f8f8;padding:8px;border-radius:4px;"
            f"line-height:1.5;color:#333;'>{code_html}</div>"
        )
        self.skill_detail.setHtml(html)

    def _delete_skill(self):
        """删除选中的技能"""
        if not self.skill_registry:
            return
        selected = self.skill_list.selectedItems()
        if not selected:
            return
        reply = QMessageBox.question(
            self, "确认", "确定删除选中的自定义技能？删除后无法恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for item in selected:
                name = item.data(Qt.UserRole)
                if name:
                    self.skill_registry.remove_skill(name)
            self._refresh_all()

    # ==================== 文档导入 ====================

    def _select_document(self):
        """第一步：选择文档文件"""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "选择教材/文献",
            "",
            "支持的文件 (*.pdf *.txt *.md);;PDF文件 (*.pdf);;"
            "文本文件 (*.txt *.md);;所有文件 (*)"
        )
        if not filepath:
            return

        if filepath.lower().endswith(".pdf"):
            try:
                import fitz  # noqa: F401
            except ImportError:
                QMessageBox.warning(
                    self, "缺少依赖",
                    "读取 PDF 需要安装 PyMuPDF 库。\n\n"
                    "请在终端运行:\n  pip install PyMuPDF\n\n"
                    "安装后重新打开此对话框即可导入 PDF。"
                )
                return

        import os
        self._pending_filepath = filepath
        filename = os.path.basename(filepath)
        self.file_label.setText(filename)
        self.file_label.setStyleSheet("color:#2c3e50; font-size:12px; padding:0 4px;")
        self.file_label.setToolTip(filepath)
        self.learn_btn.setEnabled(True)

    def _start_learning(self):
        """第二步：点击学习，开始从文档提取知识"""
        if not hasattr(self, '_pending_filepath') or not self._pending_filepath:
            return

        category = self.import_category_combo.currentData()
        confidence = 0.95

        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_label.setText("准备学习...")
        self.progress_label.setVisible(True)
        self.learn_btn.setEnabled(False)
        self.import_btn.setEnabled(False)

        self._import_worker = DocumentImportWorker(
            self._pending_filepath, self.knowledge_store, category, confidence,
            llm_config=self.llm_config
        )
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.start()

    def _on_import_progress(self, current: int, total: int, message: str):
        """导入进度回调"""
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)

    def _on_import_finished(self, result: dict):
        """导入完成回调"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.import_btn.setEnabled(True)
        self.learn_btn.setEnabled(False)
        self._pending_filepath = None
        self.file_label.setText("未选择文件")
        self.file_label.setStyleSheet("color:#999; font-size:12px; padding:0 4px;")
        self.file_label.setToolTip("")
        self._import_worker = None

        if result.get("status") == "error":
            QMessageBox.warning(self, "导入失败", result.get("message", "未知错误"))
        else:
            msg = (
                f"文档导入完成！\n\n"
                f"来源: {result.get('source', '?')}\n"
                f"总段落数: {result.get('total_chunks', 0)}\n"
                f"成功导入: {result.get('imported', 0)} 条\n"
                f"跳过（相关度低）: {result.get('skipped_low_relevance', 0)} 条\n"
                f"跳过（已存在）: {result.get('skipped_duplicate', 0)} 条"
            )
            if result.get("pages"):
                msg += f"\nPDF页数: {result['pages']}"
            tables = result.get("tables_extracted", 0)
            images = result.get("images_processed", 0)
            if tables or images:
                ai_used = result.get("ai_vision", False)
                mode = "AI视觉" if ai_used else "文本/OCR"
                msg += f"\n\n增强识别（{mode}模式）:"
                if tables:
                    msg += f"\n  表格提取: {tables} 个"
                if images:
                    msg += f"\n  图片处理: {images} 处"
                if not ai_used and not result.get("ocr_available", False):
                    msg += ("\n\n提示: 连接LLM后导入可启用AI视觉识别，"
                            "获得更准确的图片和表格识别效果。")
            QMessageBox.information(self, "导入成功", msg)
            self._refresh_all()


class HistoryDialog(QDialog):
    """历史对话管理对话框 — 查看、加载和删除历史对话记录"""

    # 信号：用户选择加载某条历史
    load_requested = pyqtSignal(str)  # session_id

    def __init__(self, memory_store, parent=None):
        super().__init__(parent)
        self._memory_store = memory_store
        self._sessions = []
        self.setWindowTitle("历史对话记录")
        self.setMinimumSize(600, 420)
        try:
            from PyQt5.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen().availableGeometry()
            w = min(760, int(screen.width() * 0.5))
            h = min(560, int(screen.height() * 0.55))
            self.resize(w, h)
        except Exception:
            self.resize(700, 500)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel("历史对话记录")
        title.setStyleSheet(
            "font-size:18px; font-weight:bold; color:#2c3e50; margin-bottom:2px;"
        )
        layout.addWidget(title)

        hint = QLabel("选择一条对话历史可查看摘要。支持加载到当前会话或删除。")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#7f8c8d; font-size:12px; margin-bottom:4px;")
        layout.addWidget(hint)

        splitter = QSplitter(Qt.Vertical)

        # 会话列表
        self.session_list = QListWidget()
        self.session_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.session_list.currentRowChanged.connect(self._on_session_selected)
        self.session_list.setStyleSheet("""
            QListWidget {
                border:1px solid #e0e0e0; border-radius:6px;
                font-size:13px; background:white; outline:none;
            }
            QListWidget::item {
                padding:8px 12px; border-bottom:1px solid #f0f0f0;
            }
            QListWidget::item:selected { background-color:#d5e8f6; color:#000; }
            QListWidget::item:hover:!selected { background-color:#f5f9ff; }
        """)
        splitter.addWidget(self.session_list)

        # 摘要预览
        self.preview = QTextBrowser()
        self.preview.setOpenExternalLinks(False)
        self.preview.setStyleSheet("""
            QTextBrowser {
                border:1px solid #e0e0e0; border-radius:6px;
                padding:10px; font-size:13px; background:#fafbfc;
            }
        """)
        splitter.addWidget(self.preview)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        # 按钮栏
        btn_bar = QHBoxLayout()
        btn_bar.setSpacing(8)

        load_btn = QPushButton("加载到当前会话")
        load_btn.clicked.connect(self._load_session)
        load_btn.setStyleSheet("""
            QPushButton { background-color:#3498db; color:white;
                          padding:6px 18px; border:none; border-radius:5px;
                          font-size:13px; font-weight:bold; }
            QPushButton:hover { background-color:#2980b9; }
        """)
        btn_bar.addWidget(load_btn)

        del_btn = QPushButton("删除选中")
        del_btn.clicked.connect(self._delete_sessions)
        del_btn.setStyleSheet("""
            QPushButton { background-color:#e74c3c; color:white;
                          padding:6px 18px; border:none; border-radius:5px;
                          font-size:13px; }
            QPushButton:hover { background-color:#c0392b; }
        """)
        btn_bar.addWidget(del_btn)

        btn_bar.addStretch()

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        close_btn.setStyleSheet("""
            QPushButton { background-color:#95a5a6; color:white;
                          padding:6px 22px; border:none; border-radius:5px;
                          font-size:13px; }
            QPushButton:hover { background-color:#7f8c8d; }
        """)
        btn_bar.addWidget(close_btn)

        layout.addLayout(btn_bar)

    def _refresh(self):
        """刷新会话列表"""
        import time as _time
        self._sessions = self._memory_store.list_sessions()
        self.session_list.clear()
        self.preview.clear()
        for sess in self._sessions:
            ts = _time.strftime(
                "%Y-%m-%d %H:%M", _time.localtime(sess["timestamp"])
            )
            text = f"[{ts}]  {sess['message_count']} 条消息  |  {sess['session_id']}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, sess["session_id"])
            self.session_list.addItem(item)

    def _on_session_selected(self, row: int):
        """选中某条会话时显示摘要"""
        if row < 0 or row >= len(self._sessions):
            self.preview.clear()
            return
        sess = self._sessions[row]
        msgs = self._memory_store.load_session(sess["session_id"])
        if not msgs:
            self.preview.setHtml("<i>无法加载此会话</i>")
            return

        import time as _time
        ts = _time.strftime(
            "%Y-%m-%d %H:%M:%S", _time.localtime(sess["timestamp"])
        )
        html = (
            f"<div style='font-weight:bold;font-size:14px;color:#2c3e50;"
            f"margin-bottom:6px;'>会话: {sess['session_id']}</div>"
            f"<div style='font-size:12px;color:#888;margin-bottom:8px;'>"
            f"时间: {ts} &nbsp;|&nbsp; 消息数: {sess['message_count']}</div>"
            f"<hr style='border:none;border-top:1px solid #eee;'>"
        )
        # 显示前10条消息摘要
        count = 0
        for msg in msgs:
            if count >= 10:
                html += "<div style='color:#999;font-size:12px;'>... (更多消息)</div>"
                break
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or role == "system" or role == "tool":
                continue
            content_preview = content[:150].replace("<", "&lt;").replace(">", "&gt;")
            if len(content) > 150:
                content_preview += "..."
            if role == "user":
                html += (
                    f"<div style='margin:4px 0;padding:4px 8px;"
                    f"background:#dceefb;border-radius:4px;font-size:12px;'>"
                    f"<b>你:</b> {content_preview}</div>"
                )
            else:
                html += (
                    f"<div style='margin:4px 0;padding:4px 8px;"
                    f"background:#f0f0f0;border-radius:4px;font-size:12px;'>"
                    f"<b>助手:</b> {content_preview}</div>"
                )
            count += 1
        self.preview.setHtml(html)

    def _load_session(self):
        """加载选中的会话"""
        selected = self.session_list.selectedItems()
        if not selected:
            QMessageBox.information(self, "提示", "请先选择一条对话历史")
            return
        session_id = selected[0].data(Qt.UserRole)
        self.load_requested.emit(session_id)
        self.accept()

    def _delete_sessions(self):
        """删除选中的会话"""
        selected = self.session_list.selectedItems()
        if not selected:
            return
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定删除选中的 {len(selected)} 条对话历史？删除后无法恢复。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            for item in selected:
                session_id = item.data(Qt.UserRole)
                self._memory_store.delete_session(session_id)
            self._refresh()


class ChatWidget(QWidget):
    """对话式热力学计算界面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.agent = None
        self.worker = None
        self.setup_ui()

    def setup_ui(self):
        """设置界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # 顶部：LLM配置工具栏（紧凑扁平）
        config_bar = self._create_config_bar()
        main_layout.addWidget(config_bar)

        # 中间：对话区域（可滚动，占满剩余空间）
        self.chat_area = self._create_chat_area()
        main_layout.addWidget(self.chat_area, stretch=1)

        # 底部：输入区域
        input_area = self._create_input_area()
        main_layout.addWidget(input_area)

    def _create_config_bar(self) -> QWidget:
        """创建LLM配置工具栏"""
        bar = QWidget()
        bar.setStyleSheet("""
            QWidget#configBar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #f8f9fa, stop:1 #eef0f2);
                border-bottom: 1px solid #d0d0d0;
            }
        """)
        bar.setObjectName("configBar")

        outer = QVBoxLayout(bar)
        outer.setSpacing(6)
        outer.setContentsMargins(12, 10, 12, 8)

        # ---- 第一行：提供商 / 地址 / 模型 / 刷新 / API Key ----
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        _L = "font-size:13px; color:#444; font-weight:bold;"
        _C = ("QComboBox { font-size:13px; padding:4px 8px; border:1px solid #bbb;"
              " border-radius:4px; background:#fff; min-height:28px; }"
              " QComboBox:focus { border-color:#3498db; }"
              " QComboBox::drop-down { border:none; width:20px; }"
              " QComboBox QAbstractItemView { font-size:13px; }")
        _E = ("QLineEdit { font-size:13px; padding:4px 8px; border:1px solid #bbb;"
              " border-radius:4px; background:#fff; min-height:28px; }"
              " QLineEdit:focus { border-color:#3498db; }")

        lbl = QLabel("提供商:")
        lbl.setStyleSheet(_L)
        row1.addWidget(lbl)
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "ollama", "openai", "claude", "gemini", "deepseek", "kimichat"
        ])
        self.provider_combo.setCurrentText("ollama")
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.setFixedWidth(110)
        self.provider_combo.setStyleSheet(_C)
        row1.addWidget(self.provider_combo)

        self.server_label = QLabel("地址:")
        self.server_label.setStyleSheet(_L)
        row1.addWidget(self.server_label)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("100.91.243.106:11434")
        self.server_input.setMinimumWidth(160)
        self.server_input.setStyleSheet(_E)
        row1.addWidget(self.server_input, stretch=1)

        lbl2 = QLabel("模型:")
        lbl2.setStyleSheet(_L)
        row1.addWidget(lbl2)
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(160)
        self.model_combo.setStyleSheet(_C)
        self._update_model_list("ollama")
        row1.addWidget(self.model_combo, stretch=1)

        self.refresh_btn = QPushButton("刷新模型")
        self.refresh_btn.setToolTip("从服务器获取可用模型列表")
        self.refresh_btn.clicked.connect(self._refresh_models)
        self.refresh_btn.setFixedHeight(30)
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background:#e8e8e8; color:#444; font-size:12px;
                border:1px solid #bbb; border-radius:4px;
                padding: 2px 10px; font-weight:bold;
            }
            QPushButton:hover { background:#d8d8d8; border-color:#999; }
        """)
        row1.addWidget(self.refresh_btn)

        # API Key（仅非本地模型时显示）
        self.api_key_label = QLabel("Key:")
        self.api_key_label.setStyleSheet(_L)
        row1.addWidget(self.api_key_label)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("API Key")
        self.api_key_input.setMinimumWidth(120)
        self.api_key_input.setStyleSheet(_E)
        row1.addWidget(self.api_key_input)
        self.api_key_label.setVisible(False)
        self.api_key_input.setVisible(False)

        outer.addLayout(row1)

        # ---- 第二行：连接 / 状态 / 记忆管理 / 知识库管理 ----
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        self.connect_btn = QPushButton("  连接  ")
        self.connect_btn.clicked.connect(self._connect_llm)
        self.connect_btn.setFixedHeight(30)
        self.connect_btn.setCursor(Qt.PointingHandCursor)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background:#3498db; color:#fff; font-size:13px;
                border:none; border-radius:4px; font-weight:bold;
                padding: 2px 16px;
            }
            QPushButton:hover { background:#2980b9; }
        """)
        row2.addWidget(self.connect_btn)

        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet(
            "color:#e74c3c; font-size:13px; font-weight:bold;"
        )
        row2.addWidget(self.status_label)

        row2.addStretch()

        self.memory_btn = QPushButton("  记忆管理  ")
        self.memory_btn.setToolTip("查看和管理AI助手的持久记忆")
        self.memory_btn.clicked.connect(self._open_memory_dialog)
        self.memory_btn.setFixedHeight(30)
        self.memory_btn.setCursor(Qt.PointingHandCursor)
        self.memory_btn.setStyleSheet("""
            QPushButton {
                background:#8e44ad; color:#fff; font-size:13px;
                padding:2px 14px; border:none; border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover { background:#7d3c98; }
        """)
        row2.addWidget(self.memory_btn)

        self.knowledge_btn = QPushButton("  知识库管理  ")
        self.knowledge_btn.setToolTip("查看AI学到的领域知识和用户提供的实验数据")
        self.knowledge_btn.clicked.connect(self._open_knowledge_dialog)
        self.knowledge_btn.setFixedHeight(30)
        self.knowledge_btn.setCursor(Qt.PointingHandCursor)
        self.knowledge_btn.setStyleSheet("""
            QPushButton {
                background:#16a085; color:#fff; font-size:13px;
                padding:2px 14px; border:none; border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover { background:#138d75; }
        """)
        row2.addWidget(self.knowledge_btn)

        self.history_btn = QPushButton("  历史记录  ")
        self.history_btn.setToolTip("查看、加载和删除历史对话记录")
        self.history_btn.clicked.connect(self._open_history_dialog)
        self.history_btn.setFixedHeight(30)
        self.history_btn.setCursor(Qt.PointingHandCursor)
        self.history_btn.setStyleSheet("""
            QPushButton {
                background:#e67e22; color:#fff; font-size:13px;
                padding:2px 14px; border:none; border-radius:4px;
                font-weight:bold;
            }
            QPushButton:hover { background:#d35400; }
        """)
        row2.addWidget(self.history_btn)

        outer.addLayout(row2)

        return bar

    def _create_chat_area(self) -> QScrollArea:
        """创建对话区域"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                border-top: none;
                background: #f5f6f8;
            }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0; border-radius: 3px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #a0a0a0; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

        # 消息容器
        self.messages_container = QWidget()
        self.messages_container.setStyleSheet("background: #f5f6f8;")
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignTop)
        self.messages_layout.setSpacing(4)
        self.messages_layout.setContentsMargins(8, 8, 8, 8)

        # 欢迎消息
        welcome = QLabel(
            "欢迎使用对话式热力学计算助手！\n\n"
            "您可以用自然语言描述计算需求，例如：\n"
            "• 计算Al-5%Cu合金的液相线温度\n"
            "• 铝中每增加1%铜，熔点会降低多少？\n"
            "• 计算Fe-0.2%C合金中C的析出温度\n"
            "• 获取Fe元素的热力学性质\n"
            "• 绘制Cu含量对Al合金液相线温度的影响图\n\n"
            "请先在上方配置LLM后端并点击\"连接\"按钮。\n"
            "模型下拉框可编辑，支持手动输入自定义模型名称。"
        )
        welcome.setWordWrap(True)
        welcome.setStyleSheet("""
            color: #555; font-size: 13px; line-height: 1.5;
            padding: 16px; background: #fff;
            border-radius: 8px; border: 1px solid #e8e8e8;
        """)
        self.messages_layout.addWidget(welcome)
        self.messages_layout.addStretch()

        scroll.setWidget(self.messages_container)
        return scroll

    def _create_input_area(self) -> QWidget:
        """创建输入区域"""
        bar = QWidget()
        bar.setObjectName("inputBar")
        bar.setStyleSheet("""
            QWidget#inputBar {
                background: #fff;
                border-top: 1px solid #d0d0d0;
            }
        """)
        bar.setFixedHeight(96)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("输入您的问题… (Ctrl+Enter 发送)")
        self.input_text.setFixedHeight(72)
        self.input_text.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ccc; border-radius: 10px;
                padding: 8px 14px; font-size: 15px;
                background: #f5f6f8;
            }
            QTextEdit:focus { border-color: #3498db; background: #fff; }
        """)
        self.input_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.input_text)

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        self.send_btn.setFixedSize(72, 72)
        self.send_btn.setCursor(Qt.PointingHandCursor)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60; color: #fff;
                border: none; border-radius: 10px;
                font-weight: bold; font-size: 15px;
            }
            QPushButton:hover { background: #219a52; }
            QPushButton:disabled { background: #ccc; color: #fff; }
        """)
        layout.addWidget(self.send_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_chat)
        self.clear_btn.setFixedSize(72, 72)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #e0e0e0; color: #555;
                border: none; border-radius: 10px;
                font-size: 14px; font-weight:bold;
            }
            QPushButton:hover { background: #d0d0d0; color: #333; }
        """)
        layout.addWidget(self.clear_btn)

        return bar

    def _on_provider_changed(self, provider: str):
        """提供商变更处理"""
        self._update_model_list(provider)

        is_ollama = (provider == "ollama")

        # 仅ollama显示服务器地址和刷新按钮
        self.server_label.setVisible(is_ollama)
        self.server_input.setVisible(is_ollama)
        self.refresh_btn.setVisible(is_ollama)

        # 仅非ollama显示API Key
        self.api_key_label.setVisible(not is_ollama)
        self.api_key_input.setVisible(not is_ollama)

        if not is_ollama:
            placeholders = {
                "openai": "sk-...",
                "claude": "sk-ant-...",
                "gemini": "AIza...",
                "deepseek": "sk-...",
                "kimichat": "sk-..."
            }
            self.api_key_input.setPlaceholderText(placeholders.get(provider, "请输入API Key"))

    def _get_ollama_base(self) -> str:
        """获取当前Ollama服务器地址"""
        addr = self.server_input.text().strip()
        if not addr:
            return "http://100.91.243.106:11434"
        if not addr.startswith("http"):
            addr = f"http://{addr}"
        return addr.rstrip("/")

    # Ollama 默认模型列表（当无法连接服务器时使用）
    _OLLAMA_FALLBACK_MODELS = [
        "qwen3:8b", "qwen3:4b", "qwen2.5:7b",
        "llama3.1:8b", "llama3.2:3b", "llama3.3:latest",
        "mistral:7b",
    ]

    @staticmethod
    def _fetch_ollama_models_sync(base_url: str) -> list:
        """从Ollama服务获取已安装的模型列表（静态方法，可在子线程调用）"""
        import urllib.request
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                return sorted(models) if models else []
        except Exception:
            return []

    def _refresh_models(self):
        """异步刷新Ollama模型列表（不阻塞UI）"""
        base = self._get_ollama_base()
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("刷新中...")

        worker = _OllamaModelWorker(base)
        worker.finished_signal.connect(lambda models: self._on_models_fetched(models, base))
        self._model_worker = worker  # 防止被GC回收
        worker.start()

    def _on_models_fetched(self, models: list, base: str):
        """模型列表获取完成的回调"""
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("刷新模型")
        prev_text = self.model_combo.currentText()
        self.model_combo.clear()
        if models:
            self.model_combo.addItems(models)
        else:
            self.model_combo.addItems(self._OLLAMA_FALLBACK_MODELS)
            self._add_system_message(
                f"无法从 {base} 获取模型列表，已显示默认列表，也可手动输入模型名。"
            )
        self._mark_non_tool_models()
        # 尝试恢复之前选中的模型
        if prev_text:
            idx = self.model_combo.findText(prev_text)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
            else:
                self.model_combo.setEditText(prev_text)

    def _update_model_list(self, provider: str):
        """更新模型列表（ollama自动检测本地已安装模型）"""
        self.model_combo.clear()

        if provider == "ollama":
            # 先显示默认列表避免空白，然后异步拉取真实列表
            self.model_combo.addItems(self._OLLAMA_FALLBACK_MODELS)
            self._mark_non_tool_models()
            # 异步获取真实列表
            base = self._get_ollama_base()
            worker = _OllamaModelWorker(base)
            worker.finished_signal.connect(
                lambda models: self._on_models_fetched(models, base) if models else None
            )
            self._model_worker = worker
            worker.start()
            return

        model_lists = {
            "openai": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3", "o3-mini", "o4-mini"],
            "claude": ["claude-sonnet-4-5-20250929", "claude-opus-4-6", "claude-haiku-4-5-20251001",
                        "claude-sonnet-4-20250514", "claude-opus-4-20250514"],
            "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
            "kimichat": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]
        }

        self.model_combo.addItems(model_lists.get(provider, []))

    def _mark_non_tool_models(self):
        """标记不支持工具调用的Ollama模型（仅提示，不禁用选择）"""
        first_capable = -1
        for i in range(self.model_combo.count()):
            name = self.model_combo.itemText(i)
            if _is_tool_capable(name):
                if first_capable == -1:
                    first_capable = i
            else:
                # 仅追加提示文字，不禁用，用户仍可选择
                self.model_combo.setItemText(i, f"{name}  (不支持工具调用)")
        # 默认选中第一个支持工具调用的模型（如果有）
        if first_capable >= 0:
            self.model_combo.setCurrentIndex(first_capable)

    def _connect_llm(self):
        """连接LLM后端"""
        # 保存旧会话
        if self.agent:
            try:
                self.agent.save_session()
            except Exception:
                pass

        provider = self.provider_combo.currentText()
        api_key = self.api_key_input.text().strip() or None

        # 获取当前选择的模型名
        model = self.model_combo.currentText()
        # 清理模型名中的能力标注后缀
        model = re.sub(r'\s*\(不支持工具调用\)\s*$', '', model).strip()

        if not model:
            QMessageBox.warning(self, "无可用模型", "请先选择或输入一个模型名称。")
            return

        # 构建自定义base_url
        base_url = None
        if provider == "ollama":
            ollama_base = self._get_ollama_base()
            base_url = ollama_base.rstrip("/") + "/v1"

        try:
            from llm.chat_agent import ChatAgent

            self.agent = ChatAgent(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
                on_tool_call=self._on_tool_called
            )

            # 初始化客户端（不做阻塞式模型验证，首次聊天时自然检测）
            if hasattr(self.agent.backend, '_get_client'):
                self.agent.backend._get_client()

            self.status_label.setText(f"已连接: {model}")
            self.status_label.setStyleSheet("color: #27ae60; font-size:13px; font-weight: bold;")
            self.send_btn.setEnabled(True)
            self.connect_btn.setText("重新连接")

            # 清空当前显示，准备恢复历史
            self._clear_chat_display()

            # 显示连接、记忆和知识库状态
            mem_count = len(self.agent.memory.get_all())
            k_stats = self.agent.knowledge.get_stats()
            conn_msg = f"已成功连接到 {provider} ({model})"
            if mem_count > 0:
                conn_msg += f"  |  已加载 {mem_count} 条记忆"
            if k_stats["knowledge_count"] > 0 or k_stats["user_data_count"] > 0:
                conn_msg += (f"  |  知识库: {k_stats['knowledge_count']} 条知识, "
                             f"{k_stats['user_data_count']} 条实验数据")
            skill_count = self.agent.skill_registry.get_skill_count()
            if skill_count > 0:
                conn_msg += f"  |  自定义技能: {skill_count} 个"
            self._add_system_message(conn_msg)

            # 恢复上次对话历史到GUI
            restored_msgs = self.agent.get_restored_messages()
            if restored_msgs:
                self._add_system_message(
                    f"-- 已恢复上次对话历史 ({len(restored_msgs)} 条消息) --"
                )
                for msg in restored_msgs:
                    if msg["role"] == "user":
                        self._add_user_message(msg["content"])
                    else:
                        self._add_assistant_message(msg["content"])
                self._add_system_message("-- 历史对话结束，请继续提问 --")

        except Exception as e:
            self.agent = None
            QMessageBox.critical(self, "连接失败", f"无法连接LLM后端:\n{str(e)}")
            self.status_label.setText("连接失败")
            self.status_label.setStyleSheet("color: #e74c3c; font-size:13px; font-weight: bold;")

    def _open_memory_dialog(self):
        """打开记忆管理对话框"""
        from llm.memory import MemoryStore
        store = self.agent.memory if self.agent else MemoryStore()
        dlg = MemoryDialog(store, parent=self)
        dlg.exec_()
        # 如果已连接，刷新系统提示中的记忆
        if self.agent:
            mem_count = len(store.get_all())
            if mem_count > 0:
                self._add_system_message(f"记忆已更新，当前共 {mem_count} 条")

    def _open_knowledge_dialog(self):
        """打开知识库管理对话框"""
        from llm.knowledge import KnowledgeStore
        store = self.agent.knowledge if self.agent else KnowledgeStore()
        # 获取当前LLM配置，用于AI视觉识别
        llm_config = None
        if self.agent:
            provider = self.provider_combo.currentText().lower()
            api_key = self.api_key_input.text().strip() or None
            model = self.model_combo.currentText()
            base_url = None
            if provider == "ollama":
                base_url = self._get_ollama_base()
            llm_config = {"provider": provider, "api_key": api_key,
                          "model": model, "base_url": base_url}
        skill_reg = self.agent.skill_registry if self.agent else None
        dlg = KnowledgeDialog(store, llm_config=llm_config,
                              skill_registry=skill_reg, parent=self)
        dlg.exec_()
        if self.agent:
            stats = store.get_stats()
            sk = self.agent.skill_registry.get_skill_count()
            total = stats["knowledge_count"] + stats["user_data_count"] + sk
            if total > 0:
                msg = (f"知识库已更新: {stats['knowledge_count']} 条知识, "
                       f"{stats['user_data_count']} 条实验数据")
                if sk > 0:
                    msg += f", {sk} 个自定义技能"
                self._add_system_message(msg)

    def _open_history_dialog(self):
        """打开历史对话管理对话框"""
        from llm.memory import MemoryStore
        store = self.agent.memory if self.agent else MemoryStore()
        dlg = HistoryDialog(store, parent=self)
        dlg.load_requested.connect(self._load_history_session)
        dlg.exec_()

    def _load_history_session(self, session_id: str):
        """从历史记录加载对话到当前界面"""
        from llm.memory import MemoryStore
        store = self.agent.memory if self.agent else MemoryStore()
        msgs = store.load_session(session_id)
        if not msgs:
            self._add_system_message("无法加载该对话历史")
            return

        # 清空当前显示
        self._clear_chat_display()

        # 如果已连接代理，重置并恢复消息到代理
        if self.agent:
            self.agent.reset()
            for msg in msgs:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    self.agent.session.add_message(role, content)

        # 显示消息
        self._add_system_message(
            f"-- 已加载历史对话 {session_id} ({len(msgs)} 条消息) --"
        )
        for msg in msgs:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if not content or role == "system" or role == "tool":
                continue
            if role == "user":
                self._add_user_message(content)
            elif role == "assistant":
                self._add_assistant_message(content)
        self._add_system_message("-- 历史对话结束，请继续提问 --")

    def _send_message(self):
        """发送消息"""
        message = self.input_text.toPlainText().strip()
        if not message:
            return

        if not self.agent:
            QMessageBox.warning(self, "提示", "请先连接LLM后端")
            return

        # 清空输入框
        self.input_text.clear()

        # 添加用户消息气泡
        self._add_user_message(message)

        # 切换为取消按钮
        self.send_btn.setText("取消")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #e74c3c; color: #fff;
                border: none; border-radius: 10px;
                font-weight: bold; font-size: 15px;
            }
            QPushButton:hover { background: #c0392b; }
        """)
        self.send_btn.disconnect()
        self.send_btn.clicked.connect(self._cancel_request)
        self._is_processing = True

        # 启动后台线程
        self.worker = ChatWorker(self.agent, message)
        self.worker.response_ready.connect(self._on_response_ready)
        self.worker.tool_called.connect(self._on_tool_called)
        self.worker.tool_result_ready.connect(self._on_tool_result)
        self.worker.chart_requested.connect(self._on_chart_requested)
        self.worker.error_occurred.connect(self._on_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _cancel_request(self):
        """取消当前请求"""
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait(2000)
            self._add_system_message("请求已取消")
            self._restore_send_button()

    def _add_user_message(self, text: str):
        """添加用户消息"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        bubble = MessageBubble(text, is_user=True)
        self.messages_layout.addWidget(bubble)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _add_assistant_message(self, text: str):
        """添加助手消息"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        bubble = MessageBubble(text, is_user=False)
        self.messages_layout.addWidget(bubble)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _add_system_message(self, text: str):
        """添加系统消息"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet("""
            color: #999; font-size: 11px; font-style: italic;
            padding: 3px 10px; background: transparent;
        """)
        self.messages_layout.addWidget(label)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _add_tool_call(self, tool_name: str, arguments: dict):
        """添加工具调用显示"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        bubble = ToolCallBubble(tool_name, arguments)
        self.messages_layout.addWidget(bubble)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _add_chart(self, chart_data: dict):
        """添加图表到对话区域"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        bubble = ChartBubble(chart_data)
        self.messages_layout.addWidget(bubble)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _on_chart_requested(self, chart_data: dict):
        """图表绘制回调"""
        self._add_chart(chart_data)

    # 工具名→活动描述
    _TOOL_ACTIVITY = {
        "calculate_liquidus_temperature": "计算液相线温度",
        "calculate_precipitation_temperature": "计算析出温度",
        "calculate_activity": "计算活度",
        "calculate_activity_coefficient": "计算活度系数",
        "calculate_mixing_enthalpy": "计算混合焓",
        "calculate_gibbs_energy": "计算Gibbs自由能",
        "get_interaction_coefficient": "查询交互作用系数",
        "calculate_all_properties": "计算全部热力学性质",
        "screen_elements_liquidus_effect": "筛选元素影响",
        "search_knowledge": "检索知识库",
        "learn_knowledge": "学习新知识",
        "optimize_knowledge": "优化知识库",
        "update_experimental_value": "保存实验数据",
        "create_custom_tool": "创建自定义技能",
        "plot_chart": "绘制图表",
    }

    def _on_tool_called(self, tool_name: str, arguments: dict):
        """工具调用回调 — 显示当前操作提示"""
        activity = self._TOOL_ACTIVITY.get(tool_name, "处理中")
        if tool_name.startswith("skill_"):
            activity = f"执行技能: {tool_name[6:]}"
        self._show_thinking_indicator(activity + "...")

    def _on_tool_result(self, tool_name: str, result_json: str):
        """工具结果回调 — 不显示原始结果，等待LLM整理后输出"""
        pass

    def _add_tool_result(self, tool_name: str, result_json: str):
        """添加工具执行结果显示"""
        # 移除stretch
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        bubble = ToolResultBubble(tool_name, result_json)
        self.messages_layout.addWidget(bubble)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _show_thinking_indicator(self, text: str = "正在处理..."):
        """显示活动指示"""
        # 如果已有 thinking label，更新文本即可
        if hasattr(self, '_thinking_label') and self._thinking_label is not None:
            self._thinking_label.setText(f"⟳  {text}")
            self._scroll_to_bottom()
            return

        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        self._thinking_label = QLabel(f"⟳  {text}")
        self._thinking_label.setWordWrap(True)
        self._thinking_label.setStyleSheet("""
            color: #3498db; font-size: 12px;
            font-style: italic; padding: 4px 10px;
        """)
        self.messages_layout.addWidget(self._thinking_label)
        self.messages_layout.addStretch()
        self._scroll_to_bottom()

    def _remove_thinking_indicator(self):
        """移除'计算中...'提示"""
        if hasattr(self, '_thinking_label') and self._thinking_label is not None:
            self.messages_layout.removeWidget(self._thinking_label)
            self._thinking_label.deleteLater()
            self._thinking_label = None

    def _on_response_ready(self, response: str):
        """响应就绪回调"""
        self._remove_thinking_indicator()
        self._add_assistant_message(response)

    def _on_error(self, error_msg: str):
        """错误回调，对常见错误提供可操作的提示"""
        self._remove_thinking_indicator()
        msg = error_msg
        lower = error_msg.lower()
        if "404" in error_msg and "not found" in lower:
            model = self.model_combo.currentText()
            model = re.sub(r'\s*\(不支持工具调用\)\s*$', '', model).strip()
            msg = (f"模型 '{model}' 不存在。请在 Ollama 服务器上执行:\n"
                   f"  ollama pull {model}\n"
                   f"或切换到已安装的模型。")
        elif "timed out" in lower or "timeout" in lower:
            msg = "请求超时，请检查 Ollama 服务器地址和网络连接。"
        elif "connection" in lower and ("refused" in lower or "error" in lower):
            msg = "无法连接到 Ollama 服务器，请检查服务是否运行。"
        self._add_system_message(f"LLM调用失败: {msg}")

    def _on_worker_finished(self):
        """工作线程完成回调"""
        self._restore_send_button()
        # 自动保存对话历史
        if self.agent:
            try:
                self.agent.save_session()
            except Exception:
                pass

    def _restore_send_button(self):
        """恢复发送按钮状态"""
        self._is_processing = False
        self.send_btn.disconnect()
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(True)
        self.send_btn.setText("发送")
        self.send_btn.setStyleSheet("""
            QPushButton {
                background: #27ae60; color: #fff;
                border: none; border-radius: 10px;
                font-weight: bold; font-size: 15px;
            }
            QPushButton:hover { background: #219a52; }
            QPushButton:disabled { background: #ccc; color: #fff; }
        """)

    def _clear_chat_display(self):
        """清空对话区域显示（不重置代理）"""
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_chat(self):
        """清空对话"""
        self._clear_chat_display()

        # 重置代理
        if self.agent:
            self.agent.reset()

        # 添加欢迎消息
        self._add_system_message("对话已清空，开始新的会话。")

    def _scroll_to_bottom(self):
        """滚动到底部"""
        QTimer.singleShot(100, lambda: self.chat_area.verticalScrollBar().setValue(
            self.chat_area.verticalScrollBar().maximum()
        ))

    def keyPressEvent(self, event):
        """键盘事件处理"""
        # Ctrl+Enter 发送消息
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self._send_message()
        else:
            super().keyPressEvent(event)
