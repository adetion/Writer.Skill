#!/usr/bin/env python3
import os
import sys
# 加入用户安装的包路径
import site
sys.path.insert(0, site.getusersitepackages())
sys.path.append('/home/node/clawd/skills/writer/scripts')
from file_parser import FileParser

# 素材目录
MATERIALS_DIR = "/home/node/clawd/novel-materials/"
# 知识库输出目录
OUTPUT_DIR = "/home/node/clawd/skills/writer/novel_knowledge/"

# 初始化解析器
parser = FileParser(output_dir=OUTPUT_DIR)

# 支持的格式
SUPPORTED_EXTS = [".docx", ".xlsx", ".pdf", ".txt", ".md"]

# 统计
total_files = 0
total_entries = 0

# 遍历所有文件
for root, dirs, files in os.walk(MATERIALS_DIR):
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in SUPPORTED_EXTS:
            file_path = os.path.join(root, file)
            try:
                print(f"正在处理: {file_path}")
                output_path, count = parser.parse_file(file_path)
                total_files += 1
                total_entries += count
                print(f"✅ 处理完成，生成{count}条条目，保存到: {output_path}")
            except Exception as e:
                print(f"❌ 处理失败 {file_path}: {str(e)}")

print(f"\n🎉 全部处理完成！共处理{total_files}个文件，生成{total_entries}条知识库条目")
