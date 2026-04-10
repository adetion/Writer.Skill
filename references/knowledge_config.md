# Knowledge Base Configuration Guide

## Knowledge Base Structure
The knowledge base is stored by default in the `./novel_knowledge/` directory and supports the following structured file formats:
- `world_setting.yaml`: Worldbuilding settings
- `characters.yaml`: Character settings
- `plot_outline.yaml`: Overall plot outline
- `custom_rules.yaml`: Custom creation rules

## File Format Requirements
Each knowledge base entry adopts the following structure to facilitate retrieval:
```yaml
- id: unique_entry_id
  title: Entry title
  content: Entry content
  tags: ["tag1", "tag2"] # Used for keyword retrieval
  priority: 1 # Retrieval priority; higher values are returned first
```
## Retrieval Rules
1、Each time content is generated, match tags and content based on keywords from the current generation prompt, prioritizing high‑priority entries.
2、The total token count of retrieval results must not exceed the configured knowledge_chunk_size value; any excess automatically truncates lower‑priority entries.
3、Recently used entries are cached in the state file to avoid redundant retrieval.
