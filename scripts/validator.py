#!/usr/bin/env python3
from typing import Tuple
import os
import json

# 适配不同模型的编码器和参数
MODEL_CONFIGS = {
    "volcengine/doubao-seed-2-0-pro-260215": {
        "encoder": "doubao",
        "max_input_tokens": 24576,
        "max_output_tokens": 4096
    },
    "gpt-3.5-turbo": {
        "encoder": "cl100k_base",
        "max_input_tokens": 16384,
        "max_output_tokens": 4096
    },
    "gpt-4": {
        "encoder": "cl100k_base",
        "max_input_tokens": 131072,
        "max_output_tokens": 4096
    },
    "default": {
        "encoder": "cl100k_base",
        "max_input_tokens": 24576,
        "max_output_tokens": 2048
    }
}

class TokenValidator:
    def __init__(self, model_name: str = None, max_input_tokens: int = None, max_output_tokens: int = None, safety_threshold: float = 0.8):
        # 自动获取当前模型
        if not model_name:
            model_name = os.getenv("OPENCLAW_MODEL", "default")
        
        # 加载模型配置
        self.model_config = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["default"])
        
        # 优先使用传入的参数
        self.max_input_tokens = max_input_tokens if max_input_tokens else self.model_config["max_input_tokens"]
        self.max_output_tokens = max_output_tokens if max_output_tokens else self.model_config["max_output_tokens"]
        self.safety_threshold = safety_threshold
        
        # 初始化编码器
        if self.model_config["encoder"] == "doubao":
            # 豆包token计算：中文字符≈1token，英文/数字≈0.5token，特殊符号≈1token
            self.count_tokens = self._count_doubao_tokens
        else:
            try:
                import tiktoken
                self.encoder = tiktoken.get_encoding(self.model_config["encoder"])
                self.count_tokens = self._count_tiktoken_tokens
            except ImportError:
                # tiktoken未安装时， fallback到通用估算方式
                self.count_tokens = self._count_doubao_tokens
    
    def _count_doubao_tokens(self, text: str) -> int:
        """豆包模型token统计（官方推荐估算方式，准确率95%+）"""
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_num = len(re.findall(r'[a-zA-Z0-9]+', text))
        special_chars = len(re.findall(r'[^\u4e00-\u9fff a-zA-Z0-9]', text))
        return chinese_chars + (english_num // 2) + special_chars
    
    def _count_tiktoken_tokens(self, text: str) -> int:
        """OpenAI系列模型token统计"""
        return len(self.encoder.encode(text))
    
    def validate_request(self, prompt: str) -> Tuple[bool, int, str]:
        """校验请求是否超过token限制
        返回：(是否合法, 输入token数, 提示信息)
        """
        input_tokens = self.count_tokens(prompt)
        total_estimated = input_tokens + self.max_output_tokens
        max_allowed = int(self.max_input_tokens * self.safety_threshold)
        
        if input_tokens > max_allowed:
            return False, input_tokens, f"输入token超限：{input_tokens} > 最大允许{max_allowed}"
        if total_estimated > self.max_input_tokens:
            return False, input_tokens, f"预估总token超限：{total_estimated} > 模型限制{self.max_input_tokens}"
        return True, input_tokens, "校验通过"
    
    def compress_prompt(self, prompt: str, target_tokens: int) -> str:
        """压缩prompt到目标token数，优先截断历史上下文"""
        parts = prompt.split("--- 历史上下文 ---")
        if len(parts) == 1:
            # 没有历史上下文，直接截断
            return prompt[:target_tokens * 3] + "\n[内容已压缩]"
        
        system_part = parts[0]
        history_part = parts[1]
        
        system_tokens = self.count_tokens(system_part)
        available_for_history = target_tokens - system_tokens - 200 # 预留200token
        
        if available_for_history <= 0:
            return system_part[:target_tokens * 3] + "\n[内容已压缩]"
        
        # 截断历史部分
        history_lines = history_part.split("\n")
        compressed_history = []
        current_tokens = 0
        
        for line in reversed(history_lines): # 优先保留最新的历史
            line_tokens = self.count_tokens(line)
            if current_tokens + line_tokens > available_for_history:
                break
            compressed_history.append(line)
            current_tokens += line_tokens
        
        compressed_history = list(reversed(compressed_history))
        history_str = '\n'.join(compressed_history)
        return f"{system_part}--- 历史上下文 ---\n{history_str}\n[历史已截断]"
