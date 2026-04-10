#!/usr/bin/env python3
import os
import yaml
from typing import List, Dict, Any
from validator import TokenValidator

class KnowledgeRetriever:
    def __init__(self, knowledge_dir: str, max_chunk_size: int = 4096, model_name: str = None):
        self.knowledge_dir = knowledge_dir
        self.max_chunk_size = max_chunk_size
        # 使用统一的token校验器，自动适配模型
        self.validator = TokenValidator(model_name=model_name)
        self.knowledge_base = self._load_knowledge_base()
    
    def _count_tokens(self, text: str) -> int:
        """统计文本token数（复用校验器的统计逻辑，适配不同模型）"""
        return self.validator.count_tokens(text)
    
    def _load_knowledge_base(self) -> List[Dict[str, Any]]:
        """加载所有知识库文件"""
        kb = []
        if not os.path.exists(self.knowledge_dir):
            os.makedirs(self.knowledge_dir, exist_ok=True)
            return kb
        
        for filename in os.listdir(self.knowledge_dir):
            if filename.endswith(".yaml") or filename.endswith(".yml"):
                path = os.path.join(self.knowledge_dir, filename)
                with open(path, 'r', encoding='utf-8') as f:
                    entries = yaml.safe_load(f)
                    if isinstance(entries, list):
                        kb.extend(entries)
        # 按优先级排序
        kb.sort(key=lambda x: x.get("priority", 0), reverse=True)
        return kb
    
    def retrieve(self, query: str, tags: List[str] = None) -> str:
        """根据查询检索相关知识库片段，总token不超过max_chunk_size"""
        relevant_entries = []
        total_tokens = 0
        
        for entry in self.knowledge_base:
            # 简单关键词匹配，可替换为向量检索
            match = False
            if tags and any(tag in entry.get("tags", []) for tag in tags):
                match = True
            if any(keyword in entry.get("content", "").lower() for keyword in query.lower().split()):
                match = True
            if not match:
                continue
            
            entry_text = f"### {entry.get('title', '')}\n{entry.get('content', '')}\n"
            entry_tokens = self._count_tokens(entry_text)
            
            if total_tokens + entry_tokens > self.max_chunk_size:
                # 剩余空间不足，截断当前条目
                available_tokens = self.max_chunk_size - total_tokens
                if available_tokens > 100: # 至少保留100token才有意义
                    truncated = entry_text[:available_tokens * 3] # 1token≈3汉字
                    relevant_entries.append(truncated + "\n[内容截断]")
                break
            
            relevant_entries.append(entry_text)
            total_tokens += entry_tokens
        
        return "\n".join(relevant_entries)
