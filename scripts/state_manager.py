#!/usr/bin/env python3
import os
import json
from typing import Dict, Any

class StateManager:
    def __init__(self, state_path: str):
        self.state_path = state_path
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load state file, initialize if not exists"""
        if os.path.exists(self.state_path):
            with open(self.state_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "progress": {
                "total_chapters": 0,
                "completed_chapters": 0,
                "completed_chunks": 0
            },
            "outline": [],
            "chunk_paths": {},
            "knowledge_cache": [],
            "next_action": "generate_outline"
        }
    
    def save_state(self) -> None:
        """Save state to file"""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w', encoding='utf-8') as f:
            json.dump(self.state, f, ensure_ascii=False, indent=2)
    
    def update_progress(self, completed_chapters: int = None, completed_chunks: int = None) -> None:
        """Update progress"""
        if completed_chapters is not None:
            self.state["progress"]["completed_chapters"] = completed_chapters
        if completed_chunks is not None:
            self.state["progress"]["completed_chunks"] = completed_chunks
        self.save_state()
    
    def set_next_action(self, action: str) -> None:
        """Set the next action"""
        self.state["next_action"] = action
        self.save_state()
    
    def add_chunk_path(self, chapter_id: int, chunk_id: int, path: str) -> None:
        """Add scene block file path"""
        chapter_key = f"chapter_{chapter_id}"
        if chapter_key not in self.state["chunk_paths"]:
            self.state["chunk_paths"][chapter_key] = {}
        self.state["chunk_paths"][chapter_key][f"chunk_{chunk_id}"] = path
        self.save_state()
    
    def get_recent_chunks(self, count: int = 2) -> list:
        """Retrieve the content of the most recently generated 'count' scene blocks"""
        chunks = []
        # Traverse generated blocks in reverse order
        for chapter_id in sorted(range(self.state["progress"]["completed_chapters"] + 1), reverse=True):
            chapter_key = f"chapter_{chapter_id}"
            if chapter_key not in self.state["chunk_paths"]:
                continue
            for chunk_id in sorted(self.state["chunk_paths"][chapter_key].keys(), key=lambda x: int(x.split("_")[1]), reverse=True):
                path = self.state["chunk_paths"][chapter_key][chunk_id]
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        chunks.append(f.read())
                    if len(chunks) >= count:
                        return list(reversed(chunks))
        return chunks
