#!/usr/bin/env python3
"""
小说内容分块生成脚本
核心功能：解决token超限问题，分块生成小说内容，自动控制每块token数量，支持断点续写
"""

import argparse
import json
import os
import re
from typing import List, Dict
from validator import TokenValidator

# 尝试导入 OpenClaw 的 LLM 模块
try:
    from openclaw import llm
    HAS_OPENCLAW = True
except ImportError:
    print("警告: 无法导入 openclaw.llm，将使用备用方案")
    HAS_OPENCLAW = False

# 加载配置
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../references/config.yaml")
config = {}
if os.path.exists(CONFIG_PATH):
    import yaml
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

# 从配置加载参数，默认值兜底
MAX_CHUNK_TOKENS = config.get("max_output_tokens", 2000)
MIN_CHAPTER_WORDS = config.get("min_chapter_words", 8000)
SAFETY_THRESHOLD = config.get("safety_threshold", 0.8)
MODEL_NAME = config.get("model", "gpt-4")  # 默认模型

# 初始化token校验器，自动适配当前模型
validator = TokenValidator(safety_threshold=SAFETY_THRESHOLD)


def load_context(context_path: str) -> Dict:
    """
    加载上下文和已生成内容
    """
    if os.path.exists(context_path):
        with open(context_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "current_chapter": 1,
        "current_position": 0,
        "generated_content": [],
        "last_paragraph": "",
        "chapter_outline": []
    }


def save_context(context: Dict, context_path: str):
    """
    保存上下文状态
    """
    with open(context_path, 'w', encoding='utf-8') as f:
        json.dump(context, f, ensure_ascii=False, indent=2)


def call_llm(prompt: str, max_tokens: int) -> str:
    """
    调用真实大模型生成内容
    优先使用 OpenClaw 的 LLM 接口，否则尝试其他方式
    """
    if HAS_OPENCLAW:
        # 使用 OpenClaw 的 LLM 接口
        try:
            response = llm.generate(
                prompt=prompt,
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=0.8,  # 适中的创造性
                top_p=0.95
            )
            return response.strip()
        except Exception as e:
            print(f"OpenClaw LLM 调用失败: {e}")
            raise
    
    # 备用方案：尝试使用 OpenAI SDK（如果可用）
    try:
        import openai
        # 假设环境变量已配置 OPENAI_API_KEY
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()
    except ImportError:
        pass
    except Exception as e:
        print(f"OpenAI 调用失败: {e}")
        raise
    
    # 如果都不可用，抛出错误
    raise RuntimeError(
        "无法调用大模型。请确保：\n"
        "1. 在 OpenClaw 环境中运行，或\n"
        "2. 已安装 openai 库并配置 API_KEY"
    )


def generate_chunk(
    outline: str,
    context: Dict,
    max_tokens: int = MAX_CHUNK_TOKENS,
    style: str = "default"
) -> Dict:
    """
    生成单块内容，自动控制token数量
    返回生成结果和更新后的上下文
    """
    # 构造生成提示（压缩空白，减少token消耗）
    prompt = f"""【上下文衔接】：{context['last_paragraph'][-300:].strip()}
【当前大纲】：{outline.strip()}
【生成要求】：
1. 继续写这段小说内容，保持风格一致
2. 单次生成内容不要超过{max_tokens}token，约1200-1500字
3. 结尾留自然断点，不要中断在句子中间
4. 符合当前章节的情节走向
【风格】：{style}
直接输出生成内容，不要加其他说明。""".strip()
    
    # 校验prompt token，超限自动压缩
    is_valid, input_tokens, msg = validator.validate_request(prompt)
    if not is_valid:
        # 自动压缩prompt，目标token为最大允许输入token的70%
        target_tokens = int(validator.max_input_tokens * validator.safety_threshold * 0.7)
        prompt = validator.compress_prompt(prompt, target_tokens)
        # 二次校验
        is_valid, input_tokens, msg = validator.validate_request(prompt)
        if not is_valid:
            raise RuntimeError(f"Prompt压缩后仍超限：{msg}")
    
    print(f"正在调用大模型生成内容... (输入token: {input_tokens})")
    
    # 调用真实大模型生成内容
    generated_text = call_llm(prompt, max_tokens)
    
    # 清理生成内容中的多余空白
    generated_text = generated_text.strip()
    
    # 统计生成的token数
    used_tokens = validator.count_tokens(generated_text)
    
    # 更新上下文
    context['last_paragraph'] = generated_text
    context['generated_content'].append(generated_text)
    context['current_position'] += used_tokens
    
    return {
        "generated_text": generated_text,
        "used_tokens": used_tokens,
        "context": context,
        "is_chapter_complete": len('\n'.join(context['generated_content'])) >= MIN_CHAPTER_WORDS
    }


def generate_chapter(
    chapter_outline: str,
    output_path: str,
    context_path: str = "chapter_context.json",
    style: str = "default"
) -> str:
    """
    生成完整一章，自动分块生成，避免token超限
    """
    context = load_context(context_path)
    context['chapter_outline'] = chapter_outline
    
    full_chapter = []
    block_count = 0
    
    while True:
        block_count += 1
        print(f"\n--- 生成第 {block_count} 块 ---")
        
        chunk_result = generate_chunk(
            outline=chapter_outline,
            context=context,
            style=style
        )
        full_chapter.append(chunk_result['generated_text'])
        context = chunk_result['context']
        
        # 保存进度
        save_context(context, context_path)
        
        print(f"已生成块 {block_count}，使用token: {chunk_result['used_tokens']}，"
              f"累计字数: {len(''.join(full_chapter))}")
        
        # 检查是否达到最小章节字数
        current_total_words = len(''.join(full_chapter))
        if chunk_result['is_chapter_complete'] or current_total_words >= MIN_CHAPTER_WORDS:
            # 可选：检查是否在自然段落结束
            break
    
    # 合并完整章节
    chapter_content = '\n'.join(full_chapter)
    
    # 保存章节内容
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(chapter_content)
    
    # 重置上下文，准备下一章
    context['current_chapter'] += 1
    context['current_position'] = 0
    context['generated_content'] = []
    context['last_paragraph'] = ""
    save_context(context, context_path)
    
    print(f"\n章节生成完成！总块数: {block_count}，总字数: {len(chapter_content)}，"
          f"保存到: {output_path}")
    return chapter_content


def main():
    parser = argparse.ArgumentParser(description="小说内容分块生成脚本（解决token超限问题）")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # 生成单块内容
    chunk_parser = subparsers.add_parser("chunk", help="生成单块内容")
    chunk_parser.add_argument("outline", help="当前内容大纲")
    chunk_parser.add_argument("--context", default="chapter_context.json", help="上下文文件路径")
    chunk_parser.add_argument("--max-tokens", type=int, default=MAX_CHUNK_TOKENS, help="单块最大token数")
    chunk_parser.add_argument("--style", default="default", help="写作风格")
    
    # 生成完整章节
    chapter_parser = subparsers.add_parser("chapter", help="生成完整章节（自动分块）")
    chapter_parser.add_argument("outline", help="章节大纲")
    chapter_parser.add_argument("output", help="输出章节文件路径")
    chapter_parser.add_argument("--context", default="chapter_context.json", help="上下文文件路径")
    chapter_parser.add_argument("--style", default="default", help="写作风格")
    chapter_parser.add_argument("--min-words", type=int, default=MIN_CHAPTER_WORDS, help="单章最小字数")
    
    # 查看当前进度
    status_parser = subparsers.add_parser("status", help="查看当前生成进度")
    status_parser.add_argument("--context", default="chapter_context.json", help="上下文文件路径")
    
    args = parser.parse_args()
    
    if args.command == "chunk":
        context = load_context(args.context)
        result = generate_chunk(args.outline, context, 
                                max_tokens=args.max_tokens, 
                                style=args.style)
        print(f"\n生成内容:\n{result['generated_text']}")
        print(f"\n使用token: {result['used_tokens']}")
        print(f"章节完成状态: {'已完成' if result['is_chapter_complete'] else '进行中'}")
        
    elif args.command == "chapter":
        generate_chapter(args.outline, args.output, 
                        context_path=args.context, 
                        style=args.style)
        
    elif args.command == "status":
        context = load_context(args.context)
        print(f"当前进度:")
        print(f"  已完成章节: {context['current_chapter'] - 1}")
        print(f"  当前章节: 第{context['current_chapter']}章")
        print(f"  当前章节已生成字数: {len(''.join(context['generated_content']))}")
        print(f"  已生成块数: {len(context['generated_content'])}")
        if context['last_paragraph']:
            print(f"  最后一段内容: {context['last_paragraph'][-100:]}...")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()