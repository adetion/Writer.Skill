#!/usr/bin/env python3
import os
import sys
# Add user-installed package paths
import site
sys.path.insert(0, site.getusersitepackages())
sys.path.append('/home/node/clawd/skills/writer/scripts')
from file_parser import FileParser

# Materials directory
MATERIALS_DIR = "/home/node/clawd/novel-materials/"
# Knowledge base output directory
OUTPUT_DIR = "/home/node/clawd/skills/writer/novel_knowledge/"

# Initialize parser
parser = FileParser(output_dir=OUTPUT_DIR)

# Supported formats
SUPPORTED_EXTS = [".docx", ".xlsx", ".pdf", ".txt", ".md"]

# Statistics
total_files = 0
total_entries = 0

# Iterate over all files
for root, dirs, files in os.walk(MATERIALS_DIR):
    for file in files:
        ext = os.path.splitext(file)[1].lower()
        if ext in SUPPORTED_EXTS:
            file_path = os.path.join(root, file)
            try:
                print(f"Processing: {file_path}")
                output_path, count = parser.parse_file(file_path)
                total_files += 1
                total_entries += count
                print(f"✅ Processing completed, generated {count} entries, saved to: {output_path}")
            except Exception as e:
                print(f"❌ Processing failed for {file_path}: {str(e)}")

print(f"\n🎉 All processing completed! Processed {total_files} file(s), generated {total_entries} knowledge base entries")
