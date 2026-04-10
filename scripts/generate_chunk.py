#!/usr/bin/env python3
"""
Novel content chunk generation script
Core function: solve token overflow issues, generate novel content in chunks, automatically control token count per chunk, support resuming from breakpoints
"""

import argparse
import json
import os
import re
from typing import List, Dict
from validator import TokenValidator

# Attempt to import OpenClaw's LLM module
try:
    from openclaw import llm
    HAS_OPENCLAW = True
except ImportError:
    print("Warning: Unable to import openclaw.llm, falling back to alternative method")
    HAS_OPENCLAW = False

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../references/config.yaml")
config = {}
if os.path.exists(CONFIG_PATH):
    import yaml
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

# Load parameters from config, with default fallbacks
MAX_CHUNK_TOKENS = config.get("max_output_tokens", 2000)
MIN_CHAPTER_WORDS = config.get("min_chapter_words", 8000)
SAFETY_THRESHOLD = config.get("safety_threshold", 0.8)
MODEL_NAME = config.get("model", "gpt-4")  # Default model

# Initialize token validator, automatically adapts to current model
validator = TokenValidator(safety_threshold=SAFETY_THRESHOLD)


def load_context(context_path: str) -> Dict:
    """
    Load context and already generated content
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
    Save context state
    """
    with open(context_path, 'w', encoding='utf-8') as f:
        json.dump(context, f, ensure_ascii=False, indent=2)


def call_llm(prompt: str, max_tokens: int) -> str:
    """
    Call the actual LLM to generate content
    Prefer using OpenClaw's LLM interface, otherwise try other methods
    """
    if HAS_OPENCLAW:
        # Use OpenClaw's LLM interface
        try:
            response = llm.generate(
                prompt=prompt,
                model=MODEL_NAME,
                max_tokens=max_tokens,
                temperature=0.8,  # Moderate creativity
                top_p=0.95
            )
            return response.strip()
        except Exception as e:
            print(f"OpenClaw LLM call failed: {e}")
            raise
    
    # Fallback: try using OpenAI SDK (if available)
    try:
        import openai
        # Assume OPENAI_API_KEY is set in environment
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
        print(f"OpenAI call failed: {e}")
        raise
    
    # If none are available, raise an error
    raise RuntimeError(
        "Unable to call LLM. Please ensure:\n"
        "1. Running in the OpenClaw environment, or\n"
        "2. Installed the openai library and configured API_KEY"
    )


def generate_chunk(
    outline: str,
    context: Dict,
    max_tokens: int = MAX_CHUNK_TOKENS,
    style: str = "default"
) -> Dict:
    """
    Generate a single chunk, automatically control token count
    Returns the generated result and updated context
    """
    # Construct generation prompt (compress whitespace to reduce token consumption)
    prompt = f"""[Context connection]: {context['last_paragraph'][-300:].strip()}
[Current outline]: {outline.strip()}
[Generation requirements]:
1. Continue writing this novel content, maintain consistent style
2. Single generation should not exceed {max_tokens} tokens, approximately 1200-1500 words
3. End with a natural breakpoint, do not cut in the middle of a sentence
4. Follow the plot direction of the current chapter
[Style]: {style}
Output the generated content directly without additional explanations.""".strip()
    
    # Validate prompt tokens, auto-compress if limit exceeded
    is_valid, input_tokens, msg = validator.validate_request(prompt)
    if not is_valid:
        # Auto-compress prompt, target tokens = 70% of max allowed input tokens
        target_tokens = int(validator.max_input_tokens * validator.safety_threshold * 0.7)
        prompt = validator.compress_prompt(prompt, target_tokens)
        # Second validation
        is_valid, input_tokens, msg = validator.validate_request(prompt)
        if not is_valid:
            raise RuntimeError(f"Prompt still exceeds limit after compression: {msg}")
    
    print(f"Calling LLM to generate content... (input tokens: {input_tokens})")
    
    # Call actual LLM to generate content
    generated_text = call_llm(prompt, max_tokens)
    
    # Clean up extra whitespace in generated content
    generated_text = generated_text.strip()
    
    # Count generated tokens
    used_tokens = validator.count_tokens(generated_text)
    
    # Update context
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
    Generate a complete chapter, automatically split into chunks to avoid token overflow
    """
    context = load_context(context_path)
    context['chapter_outline'] = chapter_outline
    
    full_chapter = []
    block_count = 0
    
    while True:
        block_count += 1
        print(f"\n--- Generating block {block_count} ---")
        
        chunk_result = generate_chunk(
            outline=chapter_outline,
            context=context,
            style=style
        )
        full_chapter.append(chunk_result['generated_text'])
        context = chunk_result['context']
        
        # Save progress
        save_context(context, context_path)
        
        print(f"Generated block {block_count}, tokens used: {chunk_result['used_tokens']}, "
              f"total word count: {len(''.join(full_chapter))}")
        
        # Check if minimum chapter word count has been reached
        current_total_words = len(''.join(full_chapter))
        if chunk_result['is_chapter_complete'] or current_total_words >= MIN_CHAPTER_WORDS:
            # Optional: check if ending at a natural paragraph boundary
            break
    
    # Merge the complete chapter
    chapter_content = '\n'.join(full_chapter)
    
    # Save chapter content
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(chapter_content)
    
    # Reset context, prepare for next chapter
    context['current_chapter'] += 1
    context['current_position'] = 0
    context['generated_content'] = []
    context['last_paragraph'] = ""
    save_context(context, context_path)
    
    print(f"\nChapter generation complete! Total blocks: {block_count}, total words: {len(chapter_content)}, "
          f"saved to: {output_path}")
    return chapter_content


def main():
    parser = argparse.ArgumentParser(description="Novel content chunk generation script (solves token overflow issues)")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Generate single chunk
    chunk_parser = subparsers.add_parser("chunk", help="Generate a single chunk")
    chunk_parser.add_argument("outline", help="Current content outline")
    chunk_parser.add_argument("--context", default="chapter_context.json", help="Context file path")
    chunk_parser.add_argument("--max-tokens", type=int, default=MAX_CHUNK_TOKENS, help="Maximum tokens per chunk")
    chunk_parser.add_argument("--style", default="default", help="Writing style")
    
    # Generate complete chapter
    chapter_parser = subparsers.add_parser("chapter", help="Generate a complete chapter (auto-chunked)")
    chapter_parser.add_argument("outline", help="Chapter outline")
    chapter_parser.add_argument("output", help="Output chapter file path")
    chapter_parser.add_argument("--context", default="chapter_context.json", help="Context file path")
    chapter_parser.add_argument("--style", default="default", help="Writing style")
    chapter_parser.add_argument("--min-words", type=int, default=MIN_CHAPTER_WORDS, help="Minimum words per chapter")
    
    # View current progress
    status_parser = subparsers.add_parser("status", help="View current generation progress")
    status_parser.add_argument("--context", default="chapter_context.json", help="Context file path")
    
    args = parser.parse_args()
    
    if args.command == "chunk":
        context = load_context(args.context)
        result = generate_chunk(args.outline, context, 
                                max_tokens=args.max_tokens, 
                                style=args.style)
        print(f"\nGenerated content:\n{result['generated_text']}")
        print(f"\nTokens used: {result['used_tokens']}")
        print(f"Chapter completion status: {'Completed' if result['is_chapter_complete'] else 'In progress'}")
        
    elif args.command == "chapter":
        generate_chapter(args.outline, args.output, 
                        context_path=args.context, 
                        style=args.style)
        
    elif args.command == "status":
        context = load_context(args.context)
        print(f"Current progress:")
        print(f"  Completed chapters: {context['current_chapter'] - 1}")
        print(f"  Current chapter: {context['current_chapter']}")
        print(f"  Words generated in current chapter: {len(''.join(context['generated_content']))}")
        print(f"  Blocks generated: {len(context['generated_content'])}")
        if context['last_paragraph']:
            print(f"  Last paragraph snippet: {context['last_paragraph'][-100:]}...")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
