#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_skill.py —— 把 Skill 安装到 AI agent 的 skills 目录。

Skill 里需要知道 yt_dl.py 的绝对路径，所以模板用 {{REPO_PATH}} 占位，
安装时替换成本仓库的实际位置。

用法：
    python install_skill.py                     # 默认装到 ~/.workbuddy/skills/
    python install_skill.py --target <目录>      # 装到指定 skills 目录
    python install_skill.py --print             # 只打印结果，不写盘
"""

import os
import sys
import shutil
import argparse

SKILL_NAME = "yt-agent-dl"
PLACEHOLDER = "{{REPO_PATH}}"


def default_target():
    """按优先级猜一个 agent 的 skills 目录。"""
    home = os.path.expanduser("~")
    cands = [
        os.path.join(home, ".workbuddy", "skills"),
        os.path.join(home, ".claude", "skills"),
        os.path.join(home, ".codebuddy", "skills"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return c
    # 都不存在就用 WorkBuddy 的，安装时自动创建
    return cands[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=None, help="skills 根目录")
    ap.add_argument("--print", dest="dry", action="store_true",
                    help="只打印将写入的内容，不写盘")
    args = ap.parse_args()

    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(repo, "skill", "SKILL.md")
    if not os.path.isfile(src):
        print("找不到模板：%s" % src)
        return 1

    text = open(src, encoding="utf-8").read()
    if PLACEHOLDER not in text:
        print("模板里没有 %s 占位符，可能已经处理过" % PLACEHOLDER)
        return 1
    text = text.replace(PLACEHOLDER, repo)

    if args.dry:
        print(text)
        return 0

    target_root = args.target or default_target()
    dest_dir = os.path.join(target_root, SKILL_NAME)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "SKILL.md")
    with open(dest, "w", encoding="utf-8") as f:
        f.write(text)

    print("已安装 Skill：%s" % dest)
    print("仓库路径：%s" % repo)
    print("\n顺手确认一下依赖是否就绪：")
    print("  cd %s" % os.path.join(repo, "scripts"))
    print("  python yt_dl.py --diagnose")
    return 0


if __name__ == "__main__":
    sys.exit(main())
