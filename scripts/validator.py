#!/usr/bin/env python3
from typing import Tuple
import os
import json

# Encoder and parameter configurations for different models
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
        # Automatically get the current model
        if not model_name:
            model_name = os.getenv("OPENCLAW_MODEL", "default")
        
        # Load model configuration
        self.model_config = MODEL_CONFIGS.get(model_name, MODEL_CONFIGS["default"])
        
        # Prioritize passed-in parameters
        self.max_input_tokens = max_input_tokens if max_input_tokens else self.model_config["max_input_tokens"]
        self.max_output_tokens = max_output_tokens if max_output_tokens else self.model_config["max_output_tokens"]
        self.safety_threshold = safety_threshold
        
        # Initialize tokenizer
        if self.model_config["encoder"] == "doubao":
            # Doubao token counting: Chinese char ≈1 token, English/digit ≈0.5 token, special symbol ≈1 token
            self.count_tokens = self._count_doubao_tokens
        else:
            try:
                import tiktoken
                self.encoder = tiktoken.get_encoding(self.model_config["encoder"])
                self.count_tokens = self._count_tiktoken_tokens
            except ImportError:
                # Fallback to generic estimation when tiktoken is not installed
                self.count_tokens = self._count_doubao_tokens
    
    def _count_doubao_tokens(self, text: str) -> int:
        """Doubao model token count (official recommended estimation, accuracy >95%)"""
        import re
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        english_num = len(re.findall(r'[a-zA-Z0-9]+', text))
        special_chars = len(re.findall(r'[^\u4e00-\u9fff a-zA-Z0-9]', text))
        return chinese_chars + (english_num // 2) + special_chars
    
    def _count_tiktoken_tokens(self, text: str) -> int:
        """OpenAI series model token count"""
        return len(self.encoder.encode(text))
    
    def validate_request(self, prompt: str) -> Tuple[bool, int, str]:
        """Validate whether the request exceeds token limits
        Returns: (is_valid, input_token_count, message)
        """
        input_tokens = self.count_tokens(prompt)
        total_estimated = input_tokens + self.max_output_tokens
        max_allowed = int(self.max_input_tokens * self.safety_threshold)
        
        if input_tokens > max_allowed:
            return False, input_tokens, f"Input token limit exceeded: {input_tokens} > maximum allowed {max_allowed}"
        if total_estimated > self.max_input_tokens:
            return False, input_tokens, f"Estimated total token limit exceeded: {total_estimated} > model limit {self.max_input_tokens}"
        return True, input_tokens, "Validation passed"
    
    def compress_prompt(self, prompt: str, target_tokens: int) -> str:
        """Compress the prompt to the target token count, truncating historical context first"""
        parts = prompt.split("--- Historical Context ---")
        if len(parts) == 1:
            # No historical context, truncate directly
            return prompt[:target_tokens * 3] + "\n[Content compressed]"
        
        system_part = parts[0]
        history_part = parts[1]
        
        system_tokens = self.count_tokens(system_part)
        available_for_history = target_tokens - system_tokens - 200  # reserve 200 tokens
        
        if available_for_history <= 0:
            return system_part[:target_tokens * 3] + "\n[Content compressed]"
        
        # Truncate historical part
        history_lines = history_part.split("\n")
        compressed_history = []
        current_tokens = 0
        
        for line in reversed(history_lines):  # Prioritize retaining the most recent history
            line_tokens = self.count_tokens(line)
            if current_tokens + line_tokens > available_for_history:
                break
            compressed_history.append(line)
            current_tokens += line_tokens
        
        compressed_history = list(reversed(compressed_history))
        history_str = '\n'.join(compressed_history)
        return f"{system_part}--- Historical Context ---\n{history_str}\n[History truncated]"
