# -*- coding: utf-8 -*-
"""pytest 公共配置：把 scripts/ 加进 import 路径（脚本无包结构，按模块导入）。"""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(SKILL_DIR, "scripts"))
