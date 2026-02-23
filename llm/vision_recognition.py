# -*- coding: utf-8 -*-
"""
Vision Recognition - AI视觉识别模块
====================================
使用多模态LLM对文档中的图片和表格进行智能识别，
替代传统OCR（Tesseract），提供更准确的内容提取。

支持的后端: OpenAI (GPT-4o), Claude, Gemini, DeepSeek, Ollama (视觉模型)
"""

import base64
from typing import Optional


# ==================== 提示词模板 ====================

_IMAGE_PROMPT = """\
请仔细分析这张图片，它来自一本材料科学/冶金热力学方面的教材或文献。
请提取图中的所有有价值信息：
1. 如果是相图/相态图：描述各相区、相界线、关键温度和成分点
2. 如果是数据曲线图：描述坐标轴含义、曲线趋势、关键数据点
3. 如果是示意图：描述其物理/化学含义
4. 如果是流程图或装置图：描述各步骤或部件
5. 任何标注的数值、符号、公式
请用中文回答，尽量提取定量信息。如果图片不包含有意义的科学内容（如装饰图、空白页等），请回答"无有效内容"。"""

_TABLE_PROMPT = """\
请仔细分析这张表格图片，它来自一本材料科学/冶金热力学方面的教材或文献。
请：
1. 完整提取表格中的所有数据
2. 保持表格结构，用Markdown表格格式输出
3. 保留所有数值、单位和符号（包括上下标）
4. 如果有表头说明或脚注，也请一并输出
请用中文回答。"""


class VisionRecognizer:
    """
    使用多模态LLM进行图片和表格识别

    参数:
        provider: LLM提供商名称 (openai, claude, gemini, ollama, deepseek, kimichat)
        api_key: API密钥
        model: 模型名称
        base_url: 自定义API地址
    """

    def __init__(self, provider: str, api_key: str = None,
                 model: str = None, base_url: str = None):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self._tested = False
        self._available = False

    def is_available(self) -> bool:
        """检测视觉识别是否可用（首次调用前返回True，之后返回实际结果）"""
        if self._tested:
            return self._available
        return True

    def recognize_image(self, image_bytes: bytes, mime_type: str = "image/png",
                        custom_prompt: str = None) -> str:
        """
        识别图片内容

        参数:
            image_bytes: 图片二进制数据
            mime_type: MIME类型 (image/png, image/jpeg 等)
            custom_prompt: 自定义提示词（不传则使用默认材料科学提示词）

        返回:
            AI识别的文本描述，失败返回空字符串
        """
        prompt = custom_prompt or _IMAGE_PROMPT
        return self._call_vision(image_bytes, mime_type, prompt)

    def recognize_table(self, image_bytes: bytes,
                        mime_type: str = "image/png") -> str:
        """
        识别表格内容，以Markdown表格格式返回

        参数:
            image_bytes: 表格图片二进制数据
            mime_type: MIME类型

        返回:
            Markdown格式的表格文本，失败返回空字符串
        """
        return self._call_vision(image_bytes, mime_type, _TABLE_PROMPT)

    # ==================== 内部方法 ====================

    def _call_vision(self, image_bytes: bytes, mime_type: str,
                     prompt: str) -> str:
        """统一调度视觉识别调用"""
        if self._tested and not self._available:
            return ""
        try:
            if self.provider in ("claude", "anthropic"):
                result = self._call_claude(image_bytes, mime_type, prompt)
            elif self.provider in ("gemini", "google"):
                result = self._call_gemini(image_bytes, mime_type, prompt)
            else:
                # OpenAI兼容: openai, deepseek, kimichat, ollama
                result = self._call_openai(image_bytes, mime_type, prompt)
            self._tested = True
            self._available = True
            return result
        except Exception:
            if not self._tested:
                self._tested = True
                self._available = False
            return ""

    def _call_openai(self, image_bytes: bytes, mime_type: str,
                     prompt: str) -> str:
        """OpenAI兼容接口的视觉调用"""
        from openai import OpenAI

        kwargs = {}
        if self.base_url:
            base = self.base_url
            if not base.endswith("/v1"):
                base = base.rstrip("/") + "/v1"
            kwargs["base_url"] = base
        kwargs["api_key"] = self.api_key or "not-needed"

        client = OpenAI(**kwargs, timeout=120)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = client.chat.completions.create(
            model=self.model or "gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{b64}"
                    }}
                ]
            }],
            max_tokens=2000
        )
        return response.choices[0].message.content.strip()

    def _call_claude(self, image_bytes: bytes, mime_type: str,
                     prompt: str) -> str:
        """Claude (Anthropic) 视觉调用"""
        import anthropic
        client = anthropic.Anthropic(api_key=self.api_key)
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        response = client.messages.create(
            model=self.model or "claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": b64
                    }},
                    {"type": "text", "text": prompt}
                ]
            }]
        )
        return response.content[0].text.strip()

    def _call_gemini(self, image_bytes: bytes, mime_type: str,
                     prompt: str) -> str:
        """Google Gemini 视觉调用"""
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model or "gemini-2.5-flash")
        # Gemini 支持直接传入字节数据
        response = model.generate_content([
            prompt,
            {"mime_type": mime_type, "data": image_bytes}
        ])
        return response.text.strip()
