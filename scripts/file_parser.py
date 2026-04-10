#!/usr/bin/env python3
import os
import yaml
import re
from typing import List, Dict, Any

class FileParser:
    SUPPORTED_FORMATS = [".docx", ".xlsx", ".pdf", ".txt", ".md"]
    
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def _get_file_type(self, file_path: str) -> str:
        """Get file type"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.SUPPORTED_FORMATS:
            return ext.lstrip(".")
        raise ValueError(f"Unsupported file format: {ext}, supported formats: {','.join(self.SUPPORTED_FORMATS)}")
    
    def parse_txt(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse txt/md file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into sections by headings
        entries = []
        sections = re.split(r'\n#{1,6}\s+', content)
        if not sections[0].strip():
            sections = sections[1:]
        
        for i, section in enumerate(sections):
            lines = section.split("\n", 1)
            title = lines[0].strip() if len(lines) > 0 else f"Entry_{i+1}"
            content = lines[1].strip() if len(lines) > 1 else section.strip()
            
            if not content:
                continue
            
            # Auto-extract tags
            tags = []
            if "Character" in title or "Role" in title:
                tags.append("Character")
            if "Worldbuilding" in title or "Setting" in title:
                tags.append("Worldbuilding")
            if "Plot" in title or "Outline" in title:
                tags.append("Plot")
            
            entries.append({
                "id": f"auto_{os.path.basename(file_path).split('.')[0]}_{i+1}",
                "title": title,
                "content": content,
                "tags": tags,
                "priority": 8 if tags else 5
            })
        return entries
    
    def parse_docx(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse docx file"""
        try:
            from docx import Document
        except ImportError:
            raise RuntimeError("Missing docx parsing dependency, please install: pip install python-docx")
        
        doc = Document(file_path)
        content = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        return self.parse_txt_content(content, os.path.basename(file_path))
    
    def parse_pdf(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse pdf file"""
        try:
            import PyPDF2
        except ImportError:
            raise RuntimeError("Missing pdf parsing dependency, please install: pip install pypdf2")
        
        content = ""
        with open(file_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                content += page.extract_text() + "\n"
        return self.parse_txt_content(content, os.path.basename(file_path))
    
    def parse_xlsx(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse xlsx file"""
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("Missing excel parsing dependency, please install: pip install openpyxl")
        
        wb = openpyxl.load_workbook(file_path)
        entries = []
        
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            data = []
            for row in sheet.iter_rows(values_only=True):
                data.append([str(cell) if cell is not None else "" for cell in row])
            
            if not data:
                continue
            
            # First row as header, subsequent rows as content
            headers = data[0]
            for i, row in enumerate(data[1:], start=1):
                row_dict = dict(zip(headers, row))
                content = "\n".join([f"{k}: {v}" for k, v in row_dict.items() if v.strip()])
                title = row_dict.get("Name", row_dict.get("title", f"{sheet_name}_Entry_{i}"))
                
                tags = [sheet_name]
                if "Character" in sheet_name:
                    tags.append("Character")
                if "Setting" in sheet_name:
                    tags.append("Worldbuilding")
                
                entries.append({
                    "id": f"auto_xlsx_{sheet_name}_{i}",
                    "title": title,
                    "content": content,
                    "tags": tags,
                    "priority": 8
                })
        return entries
    
    def parse_txt_content(self, content: str, filename: str) -> List[Dict[str, Any]]:
        """General text content parsing"""
        entries = []
        # Split by blank lines
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', content) if p.strip()]
        
        for i, para in enumerate(paragraphs):
            # Extract first sentence as title
            lines = para.split("。", 1) if "。" in para else para.split("\n", 1)
            title = lines[0].strip()[:50] if len(lines) > 0 else f"{filename.split('.')[0]}_Entry_{i+1}"
            content = para.strip()
            
            tags = []
            if "Character" in title or "Name" in content:
                tags.append("Character")
            if "Realm" in content or "World" in content or "Rule" in content:
                tags.append("Worldbuilding")
            if "Plot" in title or "Story" in content:
                tags.append("Plot")
            
            entries.append({
                "id": f"auto_{filename.split('.')[0]}_{i+1}",
                "title": title,
                "content": content,
                "tags": tags,
                "priority": 7 if tags else 5
            })
        return entries
    
    def parse_file(self, file_path: str, output_yaml: str = None) -> str:
        """Parse file and save as YAML format knowledge base"""
        file_type = self._get_file_type(file_path)
        parse_func = getattr(self, f"parse_{file_type}")
        entries = parse_func(file_path)
        
        if not output_yaml:
            output_yaml = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(file_path))[0]}.yaml")
        
        with open(output_yaml, 'w', encoding='utf-8') as f:
            yaml.dump(entries, f, allow_unicode=True, sort_keys=False)
        
        return output_yaml, len(entries)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python file_parser.py <file_path_to_parse>")
        sys.exit(1)
    
    parser = FileParser(output_dir="./")
    output_path, count = parser.parse_file(sys.argv[1])
    print(f"✅ Parsing completed, generated {count} knowledge base entries, saved to: {output_path}")
