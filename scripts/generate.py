#!/usr/bin/env python3
"""
批量生图脚本 - 读取 task.txt，逐行处理，输出日志和结果
"""
import sys
import json
import os
import time
import uuid
import logging
from datetime import datetime

# ====== 修复导入路径 ======
# 获取脚本所在目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 获取仓库根目录 (上一级)
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
# 把根目录和 module 目录都加入 Python 搜索路径
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "module"))

# 现在可以正常导入了
from module.token_manager import TokenManager
from module.api_client import ApiClient
# ====== 导入路径修复完毕 ======


def load_config():
    """加载配置"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.py")
    # 由于你的配置是 Python 文件格式，这里改为读取 config.json
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks():
    """加载 task.txt，返回提示词列表（跳过空行和注释）"""
    task_path = os.path.join(os.path.dirname(__file__), "..", "task.txt")
    if not os.path.exists(task_path):
        logger.error(f"task.txt 不存在: {task_path}")
        # 创建示例文件
        with open(task_path, "w", encoding="utf-8") as f:
            f.write("# 每行一个提示词，支持 提示词|风格|比例 格式\n")
            f.write("一支玫瑰花|油画|1:1\n")
            f.write("一只猫\n")
        logger.info(f"已创建示例 task.txt: {task_path}")
        sys.exit(0)

    with open(task_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tasks = []
    for line in lines:
        line = line.strip()
        # 跳过空行和注释
        if not line or line.startswith("#"):
            continue
        
        # 解析格式: 提示词|风格|比例
        parts = line.split("|")
        prompt = parts[0].strip()
        style = parts[1].strip() if len(parts) > 1 else None
        ratio = parts[2].strip() if len(parts) > 2 else None
        
        tasks.append({
            "prompt": prompt,
            "style": style,
            "ratio": ratio
        })

    logger.info(f"📋 共加载 {len(tasks)} 个任务")
    return tasks


def generate_single(client, prompt, style=None, ratio=None):
    """生成单张图片，返回结果字典"""
    full_prompt = prompt
    if style:
        full_prompt += f"，图风格为「{style}」"
    if ratio:
        full_prompt += f"，比例「{ratio}」"

    logger.info(f"🎨 生成: {full_prompt}")

    data = {
        "messages": [{
            "content": json.dumps({"text": full_prompt}, ensure_ascii=False),
            "content_type": 2009,
            "attachments": []
        }],
        "completion_option": {
            "is_regen": False,
            "with_suggest": False,
            "need_create_conversation": True,
            "launch_stage": 1,
            "is_replace": False,
            "is_delete": False,
            "message_from": 0,
            "event_id": "0"
        },
        "conversation_id": "0",
        "local_message_id": str(uuid.uuid1()),
        "local_conversation_id": f"local_{int(time.time() * 1000)}"
    }

    result = client.send_request(data, "/samantha/chat/completion")

    if not result:
        logger.error(f"❌ 请求失败: {prompt}")
        return {"success": False, "error": "请求失败"}

    urls = result.get("urls", [])
    if not urls:
        logger.error(f"❌ 未获取到图片: {prompt}")
        return {"success": False, "error": "未获取到图片URL"}

    logger.info(f"✅ 成功: {prompt}")
    for i, url in enumerate(urls, 1):
        logger.info(f"  [{i}] {url}")

    return {
        "success": True,
        "prompt": prompt,
        "style": style,
        "ratio": ratio,
        "urls": urls,
        "conversation_id": result.get("conversation_id"),
        "section_id": result.get("section_id")
    }


def main():
    logger.info("=" * 50)
    logger.info("🚀 豆包批量生图任务启动")
    logger.info("=" * 50)

    # 加载配置和任务
    config = load_config()
    tasks = load_tasks()

    

    # 初始化
    tm = TokenManager(config)
    client = ApiClient(tm)

    # 逐条执行
    results = []
    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks, 1):
        logger.info(f"\n--- 任务 {i}/{len(tasks)} ---")
        result = generate_single(
            client,
            task["prompt"],
            task.get("style"),
            task.get("ratio")
        )

        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

        results.append(result)
        
        # 任务间隔，避免频率限制
        if i < len(tasks):
            time.sleep(3)

    # 保存结果
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)
    result_file = os.path.join(output_dir, f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(tasks),
            "success": success_count,
            "fail": fail_count,
            "results": results
        }, f, ensure_ascii=False, indent=2)

    # 输出总结
    logger.info("\n" + "=" * 50)
    logger.info(f"📊 任务完成: 成功 {success_count}/{len(tasks)}, 失败 {fail_count}/{len(tasks)}")
    logger.info(f"📁 结果保存: {result_file}")
    logger.info(f"📋 日志保存: {log_file}")
    logger.info("=" * 50)

    # 写入 GitHub Actions summary
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## 📊 生图结果\n\n")
            f.write(f"| # | 状态 | 提示词 | 图片数量 |\n")
            f.write(f"|---|---|---|---|\n")
            for i, r in enumerate(results, 1):
                status = "✅" if r["success"] else "❌"
                prompt = r.get("prompt", "")[:30]
                count = len(r.get("urls", []))
                f.write(f"| {i} | {status} | {prompt} | {count} |\n")
            f.write(f"\n**总计: {success_count} 成功, {fail_count} 失败**\n")


if __name__ == "__main__":
    main()