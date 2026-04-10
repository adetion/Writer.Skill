# 知识库配置说明

## 知识库结构
知识库默认存储在 `./novel_knowledge/` 目录下，支持以下结构化文件格式：
- `world_setting.yaml`：世界观设定
- `characters.yaml`：人物设定
- `plot_outline.yaml`：整体剧情大纲
- `custom_rules.yaml`：自定义创作规则

## 文件格式要求
每个知识库条目采用如下结构，便于检索：
```yaml
- id: unique_entry_id
  title: 条目名称
  content: 条目内容
  tags: ["标签1", "标签2"] # 用于关键词检索
  priority: 1 # 检索优先级，数值越高越优先返回
```

## 检索规则
1. 每次生成内容时，根据当前生成提示的关键词匹配标签和内容，优先返回高优先级条目
2. 检索结果总token数不超过 `knowledge_chunk_size` 配置值，超出部分自动截断低优先级条目
3. 最近使用的条目会缓存到状态文件，避免重复检索
