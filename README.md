```yaml
---
name: writer
description: Zero-token-overflow 400-error guaranteed long-form text/novel creation assistant, supporting chunked generation, knowledge base safe retrieval, state machine persistence, fully automated creation workflow, and automatic parsing of Word(docx)/Excel(xlsx)/PDF/TXT/MD files into structured YAML knowledge bases. Activation scenarios: when the user needs to create a long novel, generate large volumes of text, manage serialized writing progress, avoid token overflow errors in large-text conversations, or import multi-format files for conversion into a YAML knowledge base.
---
```

写手Skill（长篇小说创作助手，自带知识库学习）。支持分块生成、知识库安全检索、状态机持久化、全自动创作流程，支持自动解析Word(docx)/Excel(xlsx)/PDF/TXT/MD格式文件转换为【结构化YAML知识库】。使用场景：当用户需要创作长篇小说、生成大量文本内容、管理连载写作进度、避免大文本对话导致token超限错误、需要导入多格式文件转换为YAML知识库时激活。

#  Please respect the author's hard work. Feel free to tip~~~ For the Chinese version, please visit https://gitee.com/adetion/writer-skill


# Writer Skill

## Overview
This skill is specifically designed for long-form content creation, with the core goal of **zero 400 token overflow error guarantee**. All large text exchanges are handled via file swapping; the conversation only returns status and progress information. This ensures that even in extreme scenarios such as producing 80,000 words per day, all API calls remain safe and controllable, and users need not worry about underlying token limits.

<img width="1417" height="1034" alt="截屏2026-04-11 00 38 41" src="https://github.com/user-attachments/assets/800ff458-6c59-4ce3-880c-70e7808f05f1" />


## Core Design Principles (Zero 400 Error Guarantee)
1.  For any interaction with the LLM, the sum of input tokens and output tokens is strictly controlled within 80% of the current model's limit, automatically adapting to the model's context window size (32k/128k, etc.).
2.  A strategy of "chunked generation, external storage, incremental construction" is adopted; no large text enters the conversation context.
3.  Internally driven by a state machine, each step processes only a small piece of content, avoiding per-request overflow.
4.  If a request is estimated to exceed the limit, automatic degradation (context compression, output splitting, stepwise execution) is performed, and the user is notified.

## Knowledge Base Usage Rules (Safe Retrieval Without Overflow)
1.  The knowledge base is stored as structured files (JSON/YAML) in the OpenClaw workspace, with the default path `./novel_knowledge/`. It supports vector/keyword indexing.
2.  **Multi-format automatic parsing**: Supports direct import of docx, xlsx, pdf, txt, and md files, automatically parsing and converting them into structured YAML knowledge base entries without manual formatting.
3.  Each content generation extracts only the most relevant setting fragments for the current plot; the total concatenated token count does not exceed 8k (configurable).
4.  If a knowledge base entry is too large, it is automatically truncated or an abstract is generated before being injected into the context; full content is never loaded.
5.  Knowledge base updates are performed incrementally; full data is not reloaded.

> Knowledge base configuration reference: [references/knowledge_config.md](references/knowledge_config.md)  
> File parsing script: [scripts/file_parser.py](scripts/file_parser.py)  
> Dependency installation: Run `pip install -r requirements.txt` to install all parsing dependencies.

### How to Import and Use the Knowledge Base
1.  **Automatic import**: Directly upload any supported file (docx/xlsx/pdf/txt/md); the skill automatically triggers parsing and converts it into structured YAML entries stored in the knowledge base.
2.  **Manual parsing**: Execute the command `python scripts/file_parser.py <file_path>` to manually parse a specified file.
3.  **Automatic tagging**: The parsing process automatically identifies content types, adds tags such as "Character", "Worldbuilding", "Plot", etc., and automatically sets priority levels.
4.  **File backup**: Original files are automatically backed up in the knowledge base directory without loss.

Supported file formats:
| Format | Description |
|--------|-------------|
| .docx | Word document, automatically split into entries by paragraph/heading |
| .xlsx | Excel spreadsheet, automatically converts rows into entries; first row treated as header |
| .pdf | PDF document, automatically extracts text and splits into entries |
| .txt/.md | Plain text/Markdown document, automatically split by headings/blank lines |

## Chapter Generation Rules (Stepwise Concatenation, Short Single Outputs)
### Chapter Splitting Generation
1.  A single chapter of 8000 words is split into 4–8 scene blocks (1000–2000 words each), generated block by block.
2.  Each generated scene block is immediately written to an external file; the complete chapter is not returned to the conversation.
3.  When generating the next scene block, only the 1–2 most recently generated blocks are read as context (avoiding loading the entire chapter history), while retaining necessary character/plot state.
4.  Coherence between scene blocks is automatically guaranteed by the skill; seamless concatenation occurs when writing to the file.

### Single API Call Control
1.  Before each call, automatically count tokens of the current input (system instructions + retrieved knowledge base fragments + recent scene blocks + generation prompt). If the count exceeds the safety threshold (default 24k), automatic compression is applied (reduce number of historical blocks, shorten knowledge base fragments).
2.  Single output is limited to no more than 2k tokens (approximately 1500–2000 words). This can be increased based on model capability, but total tokens must not exceed 80% of the model's limit.

> Generation script: [scripts/generate_chunk.py](scripts/generate_chunk.py)

## Conversation Interaction Rules (Minimal Messages, No Large Content Returned)
1.  All conversation replies contain only status, progress, file paths, and a small preview; each single reply does not exceed 500 words.
2.  Content exceeding 500 words (outlines, chapter text, inspection reports) is entirely written to external files; only the file path or a short summary is provided in the conversation.
3.  Upon receiving a user creation command, immediately reply with "Task started, progress will be updated in real time." Progress is gradually reported via multiple short messages (one short message per generated scene block/chapter).
4.  Supports asynchronous background execution; a summary notification is sent upon completion.

## State Machine and Persistence Rules
1.  Maintains a `novel_state.json` state file, recording:
    - Current total progress (generated chapters, number of scene blocks)
    - Pending outlines to be generated
    - File paths for each chapter / each scene block
    - Knowledge base retrieval cache (recently used settings)
    - Next action (generate outline, generate next scene block, compliance check, etc.)
2.  Each skill invocation first reads the state file to determine the execution step; after execution, updates the state before exiting.
3.  Supports resumption after interruption; if the conversation is interrupted or a token limit is triggered, continuation from the breakpoint is possible without losing progress.

> State management script: [scripts/state_manager.py](scripts/state_manager.py)

## Daily Creation Workflow (Fully Automatic, No Overflow Risk)
1.  **Generate outline**: Do not generate the full outline at once; generate outlines for 1–3 chapters at a time (1–3 sentences per chapter), write them to an outline file, and return only progress prompts each time.
2.  **Generate chapter by chapter**: Generate chapter by chapter and scene block by scene block according to the outline and state. After each block is generated, immediately write it to a file and update the state. After each chapter is completed, perform a lightweight self-check; the self-check report is written to a file.
3.  **Chapter cohesion**: When generating the first scene block of a new chapter, automatically load the last two scene blocks of the previous chapter as context to ensure plot continuity.
4.  **End-of-day final check**: After all chapters are generated, perform a full compliance check asynchronously in the background, generate a report file, and finally send a summary message: "Today's creation completed. Total X chapters. Compliance check passed. Results stored at [file path]."

## Feedback and Modification Rules (Safe Updates)
1.  When a user requests modification of a certain chapter, load only that chapter's file plus necessary knowledge base content, generate a revised version scene block by scene block, overwrite the original file, and update the state.
2.  Subsequent chapter generation automatically recognizes the modified content to maintain plot consistency.
3.  If the user pastes a large amount of material at once, automatically prompt "Material too large; please provide in batches or upload a file directly" to avoid single input overflow.

## Error Handling and Degradation Rules
1.  If an API call fails due to token overflow, automatically capture the failure, compress the input (reduce history, shorten knowledge base fragments), and retry, up to a maximum of 3 retries.
2.  If retries still fail, pause the task, send an error report file, and wait for user instructions.
3.  All error logs are written to the `./logs/writer_error.log` file for troubleshooting.

## Configurable Parameters
All parameters can be modified via [references/config.yaml](references/config.yaml):

| Parameter Name | Description | Default Value |
|----------------|-------------|----------------|
| max_input_tokens | Upper limit of input tokens per request (leave empty to auto-adapt to current model) | 24k |
| max_output_tokens | Upper limit of output tokens per request (leave empty to auto-adapt to current model) | 2k |
| safety_threshold | Safety threshold for total tokens (percentage not exceeding model limit) | 0.8 |
| context_chunks | Number of recent scene blocks to retain | 2 |
| knowledge_chunk_size | Maximum tokens for retrieved knowledge base fragments | 4k |
| work_dir | Storage directory for created content | ./novel_workspace/ |
| min_chapter_words | Minimum number of words per chapter | 8000 |
| max_retry_count | Number of retries after token overflow failure | 3 |

## Resource Description
### scripts/
- `generate_chunk.py`: Scene block generation script, responsible for token counting, content generation, and file writing.
- `state_manager.py`: State file reading/writing and breakpoint resume management.
- `knowledge_retriever.py`: Knowledge base retrieval, fragment extraction, and abstract generation.
- `validator.py`: Token overflow checking and content compliance checking.
- `file_parser.py`: Multi-format file parsing script, supports docx/xlsx/pdf/txt/md automatic conversion to structured YAML knowledge base.

### references/
- `config.yaml`: Skill parameter configuration file.
- `knowledge_config.md`: Knowledge base structure and indexing configuration description.
