# -*- coding: utf-8 -*-
"""更新配置文件路径为相对路径"""
import re
import sys

config_path = sys.argv[1]

with open(config_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换 Meilisearch 路径
content = re.sub(r'executable_path\s*=\s*"[^"]*"', 'executable_path = "meilisearch/meilisearch.exe"', content)
# 替换 db_path
content = re.sub(r'db_path\s*=\s*"[^"]*"', 'db_path = "meili_data"', content)

with open(config_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("配置文件已更新")





