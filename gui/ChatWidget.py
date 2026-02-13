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
    QAbstractItemView, QDialogButtonBox
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
                'font-size:13px;border:1px solid #c0c0c0;'
            )
            th_css = (
                'border:1px solid #b0b0b0;padding:8px 14px;'
                'background-color:#4a90d9;color:#ffffff;font-weight:bold;'
            )
            td_css_even = (
                'border:1px solid #d0d0d0;padding:7px 14px;'
                'background-color:#ffffff;'
            )
            td_css_odd = (
                'border:1px solid #d0d0d0;padding:7px 14px;'
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
        lambda m: '<div style="text-align:center;margin:6px 0;font-size:15px;">'
                  + _convert_latex_math(m.group(1)) + '</div>',
        text, flags=re.DOTALL)
    text = re.sub(
        r'\$\$(.*?)\$\$',
        lambda m: '<div style="text-align:center;margin:6px 0;font-size:15px;">'
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
    # 单字符形式: 仅当前面是希腊字母、单字母变量、或闭标签时才触发
    # 不匹配英文单词内的下划线（如 liquidus_temperature）
    # 希腊字母 + _x → 下标（如 ε_i, γ_0）
    _greek = 'αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΦΨΩ'
    text = re.sub(
        r'(?<=[' + _greek + r'>])_([a-zA-Z0-9' + _greek + r'])',
        r'<sub>\1</sub>', text)
    text = re.sub(
        r'(?<=[' + _greek + r'>])\^([a-zA-Z0-9' + _greek + r'²³⁰¹⁴⁵⁶⁷⁸⁹])',
        r'<sup>\1</sup>', text)
    # 单字母变量 + _x（仅当该单字母前面不是字母时，排除 word_word 情况）
    text = re.sub(
        r'(?<![a-zA-Z])([a-zA-Z])_([a-zA-Z0-9' + _greek + r'])',
        r'\1<sub>\2</sub>', text)
    text = re.sub(
        r'(?<![a-zA-Z])([a-zA-Z])\^([a-zA-Z0-9' + _greek + r'²³⁰¹⁴⁵⁶⁷⁸⁹])',
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
            font-size: 12px;
        """)

        # 消息内容（助手消息使用QTextBrowser渲染，支持完整HTML表格；用户消息保持QLabel）
        if is_user:
            content_label = QLabel()
            content_label.setText(text)
            content_label.setWordWrap(True)
            content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            content_label.setStyleSheet("""
                background: transparent;
                font-size: 16px;
                padding: 5px;
            """)
        else:
            content_label = QTextBrowser()
            content_label.setOpenExternalLinks(False)
            content_label.setHtml(format_message_html(text))
            content_label.setStyleSheet("""
                QTextBrowser {
                    background: transparent;
                    font-size: 16px;
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
        bg_color = "#e8f4f8" if is_user else "#f0f8e8"
        border_color = "#b8d4e3" if is_user else "#c8e6c8"
        self.setStyleSheet(f"""
            MessageBubble {{
                background-color: {bg_color};
                border: 1px solid {border_color};
                border-radius: 10px;
                margin: 5px;
            }}
        """)


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
        main_layout.setSpacing(10)

        # 顶部：LLM配置区域
        config_group = self._create_config_group()
        main_layout.addWidget(config_group)

        # 中间：对话区域（可滚动）
        self.chat_area = self._create_chat_area()
        main_layout.addWidget(self.chat_area, stretch=1)

        # 底部：输入区域
        input_area = self._create_input_area()
        main_layout.addWidget(input_area)

    def _create_config_group(self) -> QGroupBox:
        """创建LLM配置组"""
        group = QGroupBox("LLM 配置")
        layout = QHBoxLayout(group)

        # 提供商选择
        layout.addWidget(QLabel("提供商:"))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems([
            "ollama", "openai", "claude", "gemini", "deepseek", "kimichat"
        ])
        self.provider_combo.setCurrentText("ollama")
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        layout.addWidget(self.provider_combo)

        # 服务器地址（局域网Ollama等场景）
        self.server_label = QLabel("地址:")
        layout.addWidget(self.server_label)
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("localhost:11434")
        self.server_input.setMinimumWidth(150)
        self.server_input.setMaximumWidth(200)
        layout.addWidget(self.server_input)

        # 模型选择
        layout.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(200)
        self._update_model_list("ollama")
        layout.addWidget(self.model_combo)

        # 刷新模型按钮
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.setToolTip("从服务器获取可用模型列表")
        self.refresh_btn.clicked.connect(self._refresh_models)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 6px 12px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #7f8c8d; }
        """)
        layout.addWidget(self.refresh_btn)

        # API Key 输入（仅非本地模型时显示）
        self.api_key_label = QLabel("API Key:")
        layout.addWidget(self.api_key_label)
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("请输入API Key")
        self.api_key_input.setMinimumWidth(200)
        layout.addWidget(self.api_key_input)
        # 默认ollama时隐藏API Key
        self.api_key_label.setVisible(False)
        self.api_key_input.setVisible(False)

        # 连接按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.clicked.connect(self._connect_llm)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        layout.addWidget(self.connect_btn)

        # 状态指示
        self.status_label = QLabel("未连接")
        self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
        layout.addWidget(self.status_label)

        # 记忆管理按钮
        self.memory_btn = QPushButton("记忆管理")
        self.memory_btn.setToolTip("查看和管理AI助手的持久记忆（计算偏好、常用体系等）")
        self.memory_btn.clicked.connect(self._open_memory_dialog)
        self.memory_btn.setStyleSheet("""
            QPushButton {
                background-color: #8e44ad;
                color: white;
                padding: 6px 14px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #7d3c98; }
        """)
        layout.addWidget(self.memory_btn)

        layout.addStretch()

        return group

    def _create_chat_area(self) -> QScrollArea:
        """创建对话区域"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ddd;
                background: #fafafa;
                border-radius: 8px;
            }
        """)

        # 消息容器
        self.messages_container = QWidget()
        self.messages_layout = QVBoxLayout(self.messages_container)
        self.messages_layout.setAlignment(Qt.AlignTop)
        self.messages_layout.setSpacing(5)
        self.messages_layout.setContentsMargins(10, 10, 10, 10)

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
            color: #666;
            font-size: 14px;
            padding: 20px;
            background: #fff;
            border-radius: 8px;
        """)
        self.messages_layout.addWidget(welcome)
        self.messages_layout.addStretch()

        scroll.setWidget(self.messages_container)
        return scroll

    def _create_input_area(self) -> QWidget:
        """创建输入区域"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 输入框
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText("输入您的问题... (Ctrl+Enter 发送)")
        self.input_text.setMinimumHeight(80)
        self.input_text.setMaximumHeight(160)
        self.input_text.setStyleSheet("""
            QTextEdit {
                border: 2px solid #ddd;
                border-radius: 8px;
                padding: 12px;
                font-size: 16px;
                line-height: 1.5;
            }
            QTextEdit:focus {
                border-color: #3498db;
            }
        """)
        layout.addWidget(self.input_text, stretch=1)

        # 按钮容器
        btn_layout = QVBoxLayout()

        # 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self._send_message)
        self.send_btn.setEnabled(False)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                padding: 10px 25px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
        """)
        btn_layout.addWidget(self.send_btn)

        # 清空按钮
        self.clear_btn = QPushButton("清空")
        self.clear_btn.clicked.connect(self._clear_chat)
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                padding: 8px 20px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

        return widget

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
            return "http://localhost:11434"
        if not addr.startswith("http"):
            addr = f"http://{addr}"
        return addr.rstrip("/")

    def _fetch_ollama_models(self) -> list:
        """从Ollama服务获取已安装的模型列表"""
        import urllib.request
        try:
            base = self._get_ollama_base()
            req = urllib.request.Request(f"{base}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                return sorted(models) if models else []
        except Exception:
            return []

    def _refresh_models(self):
        """手动刷新Ollama模型列表"""
        models = self._fetch_ollama_models()
        self.model_combo.clear()
        if models:
            self.model_combo.addItems(models)
        else:
            base = self._get_ollama_base()
            self.model_combo.addItems(["qwen3:8b", "qwen3:4b", "llama3.2:3b", "mistral:7b"])
            self._add_system_message(f"无法连接 {base}，使用默认模型列表")
        self._mark_non_tool_models()

    def _update_model_list(self, provider: str):
        """更新模型列表（ollama自动检测本地已安装模型）"""
        self.model_combo.clear()

        if provider == "ollama":
            models = self._fetch_ollama_models()
            if models:
                self.model_combo.addItems(models)
            else:
                # ollama未运行时的回退列表
                self.model_combo.addItems(["qwen3:8b", "qwen3:4b", "llama3.2:3b", "mistral:7b"])
            self._mark_non_tool_models()
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
        """标记不支持工具调用的Ollama模型为禁用状态"""
        first_capable = -1
        for i in range(self.model_combo.count()):
            name = self.model_combo.itemText(i)
            if _is_tool_capable(name):
                if first_capable == -1:
                    first_capable = i
            else:
                # 追加提示文字并禁用该项
                self.model_combo.setItemText(i, f"{name}  (不支持工具调用)")
                item = self.model_combo.model().item(i)
                if item:
                    item.setEnabled(False)
        # 自动选中第一个支持工具调用的模型
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
        model = self.model_combo.currentText()
        # 清理模型名中的能力标注后缀
        model = re.sub(r'\s*\(不支持工具调用\)\s*$', '', model)
        api_key = self.api_key_input.text().strip() or None

        # 构建自定义base_url（仅ollama使用服务器地址输入框）
        base_url = None
        if provider == "ollama":
            addr = self.server_input.text().strip()
            if addr:
                if not addr.startswith("http"):
                    addr = f"http://{addr}"
                base_url = addr.rstrip("/") + "/v1"
            # 连接时自动刷新模型列表
            self._refresh_models()

        try:
            from llm.chat_agent import ChatAgent

            self.agent = ChatAgent(
                provider=provider,
                api_key=api_key,
                model=model,
                base_url=base_url,
                on_tool_call=self._on_tool_called
            )

            # 提前初始化客户端，验证连接是否可用
            if hasattr(self.agent.backend, '_get_client'):
                self.agent.backend._get_client()

            self.status_label.setText(f"已连接: {model}")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.send_btn.setEnabled(True)
            self.connect_btn.setText("重新连接")

            # 清空当前显示，准备恢复历史
            self._clear_chat_display()

            # 显示连接和记忆状态
            mem_count = len(self.agent.memory.get_all())
            conn_msg = f"已成功连接到 {provider} ({model})"
            if mem_count > 0:
                conn_msg += f"  |  已加载 {mem_count} 条记忆"
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
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

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
                background-color: #e74c3c;
                color: white;
                padding: 10px 25px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
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
            color: #888;
            font-size: 12px;
            font-style: italic;
            padding: 5px 10px;
            background: #f0f0f0;
            border-radius: 4px;
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

    def _on_tool_called(self, tool_name: str, arguments: dict):
        """工具调用回调 — 只显示'计算中'提示，不暴露工具细节"""
        if not hasattr(self, '_thinking_label') or self._thinking_label is None:
            self._show_thinking_indicator()

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

    def _show_thinking_indicator(self):
        """显示'计算中...'提示"""
        if self.messages_layout.count() > 0:
            item = self.messages_layout.itemAt(self.messages_layout.count() - 1)
            if item.spacerItem():
                self.messages_layout.removeItem(item)

        self._thinking_label = QLabel("正在计算中...")
        self._thinking_label.setWordWrap(True)
        self._thinking_label.setStyleSheet("""
            color: #888;
            font-size: 12px;
            font-style: italic;
            padding: 5px 10px;
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
        """错误回调"""
        self._remove_thinking_indicator()
        self._add_system_message(f"错误: {error_msg}")

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
                background-color: #27ae60;
                color: white;
                padding: 10px 25px;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
            }
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
