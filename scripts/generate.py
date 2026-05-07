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

# ====== 设置日志 (必须在最开始) ======
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)
# ====== 日志设置完毕 ======

# ====== 修复导入路径 ======
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, "module"))

# 确保 common.log 存在
import importlib.util
if importlib.util.find_spec("common") is None:
    common_dir = os.path.join(ROOT_DIR, "common")
    os.makedirs(common_dir, exist_ok=True)
    with open(os.path.join(common_dir, "__init__.py"), "w") as f:
        pass
    with open(os.path.join(common_dir, "log.py"), "w") as f:
        f.write("""
import logging, sys
logger = logging.getLogger("doubao")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
    logger.addHandler(handler)
""")

from module.token_manager import TokenManager
from module.api_client import ApiClient
# ====== 导入完成 ======


def load_config():
    """加载配置文件"""
    config_path = os.path.join(ROOT_DIR, "config.json")
    if not os.path.exists(config_path):
        logger.error(f"配置文件不存在: {config_path}")
        sys.exit(1)
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_tasks():
    """加载 task.txt，返回提示词列表"""
    task_path = os.path.join(ROOT_DIR, "task.txt")
    if not os.path.exists(task_path):
        logger.error(f"task.txt 不存在: {task_path}")
        with open(task_path, "w", encoding="utf-8") as f:
            f.write("# 每行一个提示词，支持 提示词|风格|比例 格式\n")
            f.write("一只可爱的猫|动漫|1:1\n")
        logger.info(f"已创建示例 task.txt: {task_path}")
        sys.exit(0)

    with open(task_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    tasks = []
    for line_num, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("|")
        prompt = parts[0].strip()
        style = parts[1].strip() if len(parts) > 1 else None
        ratio = parts[2].strip() if len(parts) > 2 else None

        if not prompt:
            logger.warning(f"第 {line_num} 行为空提示词，已跳过")
            continue

        tasks.append({
            "line": line_num,
            "prompt": prompt,
            "style": style,
            "ratio": ratio
        })

    logger.info(f"📋 共加载 {len(tasks)} 个任务")
    for t in tasks:
        logger.info(f"  第{t['line']}行: {t['prompt'][:40]}...")

    return tasks


def generate_single(client, task):
    """生成单张图片"""
    prompt = task["prompt"]
    style = task.get("style")
    ratio = task.get("ratio")

    full_prompt = prompt
    if style:
        full_prompt += f"，图风格为「{style}」"
    if ratio:
        full_prompt += f"，比例「{ratio}」"

    logger.info(f"🎨 [{task['line']}] {full_prompt}")

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

    try:
        result = client.send_request(data, "/samantha/chat/completion")
    except Exception as e:
        logger.error(f"❌ [{task['line']}] 请求异常: {e}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": str(e)
        }

    if not result:
        logger.error(f"❌ [{task['line']}] 请求返回空: {prompt}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": "请求返回空"
        }

    urls = result.get("urls", [])
    if not urls:
        logger.error(f"❌ [{task['line']}] 未获取到图片: {prompt}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": "未获取到图片URL",
            "raw_response": result
        }

    logger.info(f"✅ [{task['line']}] 成功: {len(urls)} 张图片")
    for i, url in enumerate(urls, 1):
        logger.info(f"    [{i}] {url}")

    return {
        "success": True,
        "line": task["line"],
        "prompt": prompt,
        "style": style,
        "ratio": ratio,
        "urls": urls,
        "conversation_id": result.get("conversation_id"),
        "section_id": result.get("section_id")
    }


def main():
    logger.info("=" * 60)
    logger.info("🚀 豆包批量生图任务启动")
    logger.info(f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 加载
    config = load_config()
    tasks = load_tasks()

    if not tasks:
        logger.warning("没有有效的任务，退出")
        return

    # 初始化
    tm = TokenManager(config)
    client = ApiClient(tm)

    # 逐条执行
    results = []
    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks, 1):
        logger.info(f"\n{'─' * 40}")
        logger.info(f"📌 任务 {i}/{len(tasks)}")
        logger.info(f"{'─' * 40}")

        result = generate_single(client, task)
        results.append(result)

        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

        # 任务间隔
        if i < len(tasks):
            logger.info("⏳ 等待 3 秒...")
            time.sleep(3)

    # 保存结果
    output_dir = os.path.join(ROOT_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    result_file = os.path.join(output_dir, f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    summary = {
        "total": len(tasks),
        "success": success_count,
        "fail": fail_count,
        "timestamp": datetime.now().isoformat(),
        "results": results
    }

    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 输出总结
    logger.info("\n" + "=" * 60)
    logger.info("📊 任务完成总结")
    logger.info(f"   总数: {len(tasks)}")
    logger.info(f"   成功: {success_count} ✅")
    logger.info(f"   失败: {fail_count} ❌")
    logger.info(f"   结果: {result_file}")
    logger.info(f"   日志: {log_file}")
    logger.info("=" * 60)

    # 失败列表
    if fail_count > 0:
        logger.warning("\n❌ 失败任务详情:")
        for r in results:
            if not r["success"]:
                logger.warning(f"   第{r['line']}行: {r['prompt'][:30]} → {r['error']}")

    # GitHub Actions summary
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## 📊 豆包生图结果\n\n")
            f.write(f"| # | 行号 | 状态 | 提示词 | 图片数 |\n")
            f.write(f"|---|---|---|---|---|\n")
            for r in results:
                status = "✅" if r["success"] else "❌"
                prompt = r.get("prompt", "")[:30]
                count = len(r.get("urls", []))
                f.write(f"| {r['line']} | {status} | {prompt} | {count} |\n")
            f.write(f"\n**总计: {success_count} 成功, {fail_count} 失败**\n")
            if fail_count > 0:
                f.write(f"\n### ❌ 失败详情\n")
                for r in results:
                    if not r["success"]:
                        f.write(f"- 第{r['line']}行: {r['prompt'][:40]} → `{r['error']}`\n")

    # 返回退出码
    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()