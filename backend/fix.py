import json
with open('chat_llm/agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('    for iteration in range(MAX_TOOL_ITERATIONS):\n        pending_tool_calls: list[dict] = []\n        has_text = False', '    last_known_player_id = None\n\n    for iteration in range(MAX_TOOL_ITERATIONS):\n        pending_tool_calls: list[dict] = []\n        has_text = False')

with open('chat_llm/agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
