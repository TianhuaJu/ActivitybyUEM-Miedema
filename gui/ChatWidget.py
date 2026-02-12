# -*- coding: utf-8 -*-
"""
Chat Widget - 对话式热力学计算界面
==================================
提供自然语言交互的热力学计算界面

作者: Claude
日期: 2026-02-12
"""

import json
from typing import Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton,
    QLabel, QComboBox, QLineEdit, QScrollArea, QFrame,
    QGroupBox, QSplitter, QMessageBox, QSizePolicy
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QColor

import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


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

        # 消息内容
        content_label = QLabel(text)
        content_label.setWordWrap(True)
        content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        content_label.setStyleSheet("""
            background: transparent;
            font-size: 14px;
            padding: 5px;
        """)

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

        # 模型选择
        layout.addWidget(QLabel("模型:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setMinimumWidth(200)
        self._update_model_list("ollama")
        layout.addWidget(self.model_combo)

        # API Key 输入
        layout.addWidget(QLabel("API Key:"))
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("本地模型无需填写")
        self.api_key_input.setMinimumWidth(200)
        layout.addWidget(self.api_key_input)

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

        # 更新API Key提示
        if provider == "ollama":
            self.api_key_input.setPlaceholderText("本地模型无需填写")
        else:
            placeholders = {
                "openai": "sk-...",
                "claude": "sk-ant-...",
                "gemini": "AIza...",
                "deepseek": "sk-...",
                "kimichat": "sk-..."
            }
            self.api_key_input.setPlaceholderText(placeholders.get(provider, "请输入API Key"))

    def _fetch_ollama_models(self) -> list:
        """从本地Ollama服务获取已安装的模型列表"""
        import urllib.request
        try:
            req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                return sorted(models) if models else []
        except Exception:
            return []

    def _update_model_list(self, provider: str):
        """更新模型列表（ollama自动检测本地已安装模型）"""
        self.model_combo.clear()

        if provider == "ollama":
            models = self._fetch_ollama_models()
            if models:
                self.model_combo.addItems(models)
                return
            # ollama未运行时的回退列表
            self.model_combo.addItems(["qwen3:8b", "qwen3:4b", "llama3.2:3b", "mistral:7b"])
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

    def _connect_llm(self):
        """连接LLM后端"""
        provider = self.provider_combo.currentText()
        model = self.model_combo.currentText()
        api_key = self.api_key_input.text().strip() or None

        try:
            from llm.chat_agent import ChatAgent

            self.agent = ChatAgent(
                provider=provider,
                api_key=api_key,
                model=model,
                on_tool_call=self._on_tool_called
            )

            # 提前初始化客户端，验证连接是否可用
            if hasattr(self.agent.backend, '_get_client'):
                self.agent.backend._get_client()

            self.status_label.setText(f"已连接: {model}")
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.send_btn.setEnabled(True)
            self.connect_btn.setText("重新连接")

            self._add_system_message(f"已成功连接到 {provider} ({model})")

        except Exception as e:
            self.agent = None
            QMessageBox.critical(self, "连接失败", f"无法连接LLM后端:\n{str(e)}")
            self.status_label.setText("连接失败")
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

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
        """工具调用回调"""
        self._add_tool_call(tool_name, arguments)

    def _on_tool_result(self, tool_name: str, result_json: str):
        """工具结果回调"""
        self._add_tool_result(tool_name, result_json)

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

    def _on_response_ready(self, response: str):
        """响应就绪回调"""
        self._add_assistant_message(response)

    def _on_error(self, error_msg: str):
        """错误回调"""
        self._add_system_message(f"错误: {error_msg}")

    def _on_worker_finished(self):
        """工作线程完成回调"""
        self._restore_send_button()

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

    def _clear_chat(self):
        """清空对话"""
        # 清空消息
        while self.messages_layout.count():
            item = self.messages_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

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
