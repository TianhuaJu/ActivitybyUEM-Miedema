# -*- coding: utf-8 -*-
"""
自定义GUI组件 (Custom GUI Widgets)
==================================
包含可复用的自定义PyQt5组件。
"""

from PyQt5.QtWidgets import QTextEdit, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QFontMetrics


class AutoResizeTextEdit(QTextEdit):
    """
    自动调整大小的文本输入框

    当输入内容较多时，自动增加高度以适应内容。
    适用于合金成分等可能较长的输入。

    特点：
    - 单行显示时与QLineEdit外观相似
    - 内容过长时自动换行并增加高度
    - 支持最小/最大行数限制
    """

    def __init__(self, parent=None, min_lines=1, max_lines=4):
        """
        初始化自动调整大小的文本输入框

        参数：
        -----
        parent : QWidget
            父组件
        min_lines : int
            最小显示行数（默认1）
        max_lines : int
            最大显示行数（默认4）
        """
        super().__init__(parent)

        self.min_lines = min_lines
        self.max_lines = max_lines

        # 设置为不换行模式（水平滚动），但允许垂直扩展
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setWordWrapMode(3)  # WrapAtWordBoundaryOrAnywhere

        # 隐藏滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 设置大小策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # 连接文本变化信号
        self.textChanged.connect(self._adjust_height)

        # 初始调整
        self._adjust_height()

    def _get_line_height(self):
        """获取单行高度"""
        fm = QFontMetrics(self.font())
        return fm.lineSpacing()

    def _adjust_height(self):
        """根据内容调整高度"""
        # 获取文档高度
        doc = self.document()
        doc.setTextWidth(self.viewport().width())
        doc_height = doc.size().height()

        # 计算行高
        line_height = self._get_line_height()

        # 计算边距
        margins = self.contentsMargins()
        frame_width = self.frameWidth()
        extra_height = margins.top() + margins.bottom() + frame_width * 2 + 4

        # 计算最小和最大高度
        min_height = line_height * self.min_lines + extra_height
        max_height = line_height * self.max_lines + extra_height

        # 计算目标高度
        target_height = int(doc_height + extra_height)
        target_height = max(min_height, min(target_height, max_height))

        # 设置固定高度
        self.setFixedHeight(target_height)

    def resizeEvent(self, event):
        """处理大小变化事件"""
        super().resizeEvent(event)
        self._adjust_height()

    def sizeHint(self):
        """返回建议大小"""
        line_height = self._get_line_height()
        margins = self.contentsMargins()
        frame_width = self.frameWidth()
        height = line_height * self.min_lines + margins.top() + margins.bottom() + frame_width * 2 + 4
        return QSize(200, height)

    def minimumSizeHint(self):
        """返回最小大小"""
        return self.sizeHint()

    def text(self):
        """
        获取文本内容（兼容QLineEdit接口）

        返回：
        -----
        str : 文本内容
        """
        return self.toPlainText()

    def setText(self, text):
        """
        设置文本内容（兼容QLineEdit接口）

        参数：
        -----
        text : str
            要设置的文本
        """
        self.setPlainText(text)

    def setPlaceholderText(self, text):
        """
        设置占位文本

        参数：
        -----
        text : str
            占位文本
        """
        super().setPlaceholderText(text)


class AutoResizeLineEdit(QTextEdit):
    """
    单行自动调整宽度的输入框

    外观类似QLineEdit，但当内容较长时会自动扩展宽度。
    适用于需要显示完整内容的场景。
    """

    def __init__(self, parent=None, min_width=150, max_width=600):
        """
        初始化

        参数：
        -----
        parent : QWidget
            父组件
        min_width : int
            最小宽度
        max_width : int
            最大宽度
        """
        super().__init__(parent)

        self.min_width = min_width
        self.max_width = max_width

        # 设置为单行模式
        self.setLineWrapMode(QTextEdit.NoWrap)

        # 隐藏滚动条
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 设置固定高度（单行）
        fm = QFontMetrics(self.font())
        line_height = fm.lineSpacing()
        margins = self.contentsMargins()
        frame_width = self.frameWidth()
        height = line_height + margins.top() + margins.bottom() + frame_width * 2 + 4
        self.setFixedHeight(height)

        # 设置大小策略
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 连接文本变化信号
        self.textChanged.connect(self._adjust_width)

    def _adjust_width(self):
        """根据内容调整宽度"""
        fm = QFontMetrics(self.font())
        text_width = fm.horizontalAdvance(self.toPlainText()) + 20

        # 限制在最小和最大宽度之间
        target_width = max(self.min_width, min(text_width, self.max_width))
        self.setMinimumWidth(target_width)

    def text(self):
        """获取文本（兼容QLineEdit）"""
        return self.toPlainText()

    def setText(self, text):
        """设置文本（兼容QLineEdit）"""
        self.setPlainText(text)
