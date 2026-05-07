#!/usr/bin/env python3
"""
批量生图脚本 - 读取 task.txt，逐行处理，输出日志和结果
保存原生豆包 API 请求和原始响应流
"""
import sys
import json
import os
import time
import uuid
import logging
import requests
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


def get_headers(config):
    """构建请求头"""
    auth = config.get('auth', {})
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "agw-js-conv": "str",
        "content-type": "application/json",
        "cookie": auth.get("cookie", ""),
        "last-event-id": "undefined",
        "origin": "https://www.doubao.com",
        "priority": "u=1, i",
        "referer": "https://www.doubao.com/chat/create-image",
        "sec-ch-ua": '"Google Chrome";v="129", "Not=A?Brand";v="8", "Chromium";v="129"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    }


def get_params(config):
    """构建请求参数"""
    auth = config.get('auth', {})
    return {
        "aid": "497858",
        "device_id": "7450669489257268771",
        "device_platform": "web",
        "language": "zh",
        "pkg_type": "release_version",
        "real_aid": "497858",
        "region": "CN",
        "samantha_web": "1",
        "sys_region": "CN",
        "tea_uuid": "7397236635946141218",
        "use-olympus-account": "1",
        "version_code": "20800",
        "web_id": "7397236635946141218",
        "msToken": auth.get("msToken", ""),
        "a_bogus": auth.get("a_bogus", "")
    }


def generate_single(config, task):
    """生成单张图片 - 直接请求豆包 API，保存原始响应流"""
    prompt = task["prompt"]
    style = task.get("style")
    ratio = task.get("ratio")

    full_prompt = prompt
    if style:
        full_prompt += f"，图风格为「{style}」"
    if ratio:
        full_prompt += f"，比例「{ratio}」"

    logger.info(f"🎨 [{task['line']}] {full_prompt}")

    # 构建请求体
    body = {
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

    # ====== 保存原始请求 ======
    raw_dir = os.path.join(ROOT_DIR, "output", "raw_api_responses")
    os.makedirs(raw_dir, exist_ok=True)

    request_file = os.path.join(raw_dir, f"task_{task['line']}_request.json")
    with open(request_file, "w", encoding="utf-8") as f:
        json.dump({
            "url": "https://www.doubao.com/samantha/chat/completion",
            "method": "POST",
            "headers": {k: v if k != "cookie" else "***隐藏***" for k, v in get_headers(config).items()},
            "params": get_params(config),
            "body": body
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"📤 请求已保存: {request_file}")
    # ====== 请求保存完毕 ======

    try:
        logger.info("📡 发送请求到豆包 API...")

        # ====== 直接发送 HTTP 请求 ======
        url = "https://www.doubao.com/samantha/chat/completion"
        headers = get_headers(config)
        params = get_params(config)

        response = requests.post(
            url,
            json=body,
            headers=headers,
            params=params,
            stream=True,
            timeout=120
        )

        logger.info(f"📡 响应状态码: {response.status_code}")

        # ====== 保存原始响应流（逐行写入，一字不改） ======
        raw_response_file = os.path.join(raw_dir, f"task_{task['line']}_raw_response.txt")
        all_raw_lines = []
        image_urls = []
        conversation_id = None
        section_id = None
        reply_id = None

        with open(raw_response_file, "w", encoding="utf-8") as raw_f:
            raw_f.write(f"=== 豆包 API 原始响应流 ===\n")
            raw_f.write(f"任务行号: {task['line']}\n")
            raw_f.write(f"提示词: {prompt}\n")
            raw_f.write(f"状态码: {response.status_code}\n")
            raw_f.write(f"响应头:\n")
            for k, v in response.headers.items():
                raw_f.write(f"  {k}: {v}\n")
            raw_f.write(f"\n=== 响应体（流式数据，每行一个事件） ===\n\n")

            for line in response.iter_lines():
                if not line:
                    continue

                decoded_line = line.decode('utf-8')
                raw_f.write(decoded_line + "\n")
                all_raw_lines.append(decoded_line)

                # ====== 同时尝试提取图片 URL（不中断流程） ======
                if decoded_line.startswith("data:"):
                    try:
                        json_str = decoded_line[5:].strip()
                        if not json_str or json_str == "[DONE]":
                            continue

                        chunk = json.loads(json_str)
                        event_data_raw = chunk.get("event_data", "{}")

                        # 安全处理 event_data
                        if isinstance(event_data_raw, str):
                            try:
                                event_data = json.loads(event_data_raw)
                            except json.JSONDecodeError:
                                continue
                        elif isinstance(event_data_raw, dict):
                            event_data = event_data_raw
                        else:
                            continue

                        if not isinstance(event_data, dict):
                            continue

                        # 提取会话信息
                        if "conversation_id" in event_data:
                            conversation_id = event_data["conversation_id"]
                        if "section_id" in event_data:
                            section_id = event_data.get("section_id")
                        if "reply_id" in event_data:
                            reply_id = event_data.get("reply_id")

                        # 提取图片 URL
                        if "message" in event_data:
                            message = event_data["message"]

                            if isinstance(message, str):
                                try:
                                    message = json.loads(message)
                                except json.JSONDecodeError:
                                    continue

                            if isinstance(message, dict) and message.get("content_type") == 2010:
                                content = message.get("content", "{}")

                                if isinstance(content, str):
                                    try:
                                        content = json.loads(content)
                                    except json.JSONDecodeError:
                                        continue

                                if isinstance(content, dict):
                                    for img_data in content.get("data", []):
                                        if isinstance(img_data, dict):
                                            image_raw = img_data.get("image_raw", {})
                                            if isinstance(image_raw, dict):
                                                url = image_raw.get("url")
                                                if url:
                                                    image_urls.append(url)
                                                    logger.info(f"[Doubao] 找到图片 URL: {url[:80]}...")
                    except Exception as e:
                        # 解析失败不影响原始数据保存
                        logger.debug(f"解析某行时出错（不影响保存）: {e}")
                        continue

        logger.info(f"📄 原始响应已保存: {raw_response_file} (共 {len(all_raw_lines)} 行)")
        # ====== 原始响应保存完毕 ======

        # ====== 保存解析后的结果 ======
        parsed_file = os.path.join(raw_dir, f"task_{task['line']}_parsed.json")
        with open(parsed_file, "w", encoding="utf-8") as f:
            json.dump({
                "task": {
                    "line": task["line"],
                    "prompt": prompt,
                    "style": style,
                    "ratio": ratio,
                    "full_prompt": full_prompt
                },
                "response": {
                    "status_code": response.status_code,
                    "image_urls": image_urls,
                    "image_count": len(image_urls),
                    "conversation_id": conversation_id,
                    "section_id": section_id,
                    "reply_id": reply_id,
                    "raw_lines_count": len(all_raw_lines)
                }
            }, f, ensure_ascii=False, indent=2)
        logger.info(f"📄 解析结果已保存: {parsed_file}")
        # ====== 解析结果保存完毕 ======

    except requests.exceptions.Timeout:
        logger.error(f"❌ [{task['line']}] 请求超时")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": "请求超时"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ [{task['line']}] 请求失败: {e}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": f"请求失败: {str(e)}"
        }
    except Exception as e:
        logger.error(f"❌ [{task['line']}] 未知错误: {e}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": f"未知错误: {str(e)}"
        }

    if not image_urls:
        logger.error(f"❌ [{task['line']}] 未提取到图片 URL")
        logger.error(f"   原始响应行数: {len(all_raw_lines)}")
        # 打印最后几行方便调试
        if all_raw_lines:
            logger.error(f"   最后 3 行原始响应:")
            for l in all_raw_lines[-3:]:
                logger.error(f"     {l[:200]}")
        return {
            "success": False,
            "line": task["line"],
            "prompt": prompt,
            "error": f"未提取到图片 URL（响应行数: {len(all_raw_lines)}）"
        }

    logger.info(f"✅ [{task['line']}] 成功: {len(image_urls)} 张图片")
    for i, url in enumerate(image_urls, 1):
        logger.info(f"    [{i}] {url}")

    return {
        "success": True,
        "line": task["line"],
        "prompt": prompt,
        "style": style,
        "ratio": ratio,
        "urls": image_urls,
        "conversation_id": conversation_id,
        "section_id": section_id,
        "reply_id": reply_id
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

    # 逐条执行
    results = []
    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks, 1):
        logger.info(f"\n{'─' * 40}")
        logger.info(f"📌 任务 {i}/{len(tasks)}")
        logger.info(f"{'─' * 40}")

        result = generate_single(config, task)
        results.append(result)

        if result["success"]:
            success_count += 1
        else:
            fail_count += 1

        # 任务间隔
        if i < len(tasks):
            logger.info("⏳ 等待 3 秒...")
            time.sleep(3)

    # 保存汇总结果
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
    logger.info(f"   汇总结果: {result_file}")
    logger.info(f"   运行日志: {log_file}")
    logger.info(f"   原始响应: output/raw_api_responses/")
    logger.info("=" * 60)

    # 失败列表
    if fail_count > 0:
        logger.warning("\n❌ 失败任务详情:")
        for r in results:
            if not r["success"]:
                logger.warning(f"   第{r['line']}行: {r['prompt'][:40]} → {r['error']}")

    # GitHub Actions summary
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(f"## 📊 豆包生图结果\n\n")
            f.write(f"| 行号 | 状态 | 提示词 | 图片数 |\n")
            f.write(f"|---|---|---|---|\n")
            for r in results:
                status = "✅" if r["success"] else "❌"
                prompt_text = r.get("prompt", "")[:25]
                count = len(r.get("urls", []))
                f.write(f"| {r['line']} | {status} | {prompt_text} | {count} |\n")
            f.write(f"\n**总计: {success_count} 成功, {fail_count} 失败**\n\n")
            f.write(f"### 📁 Artifacts 包含:\n")
            f.write(f"- `output/raw_api_responses/task_N_request.json` → 原始请求\n")
            f.write(f"- `output/raw_api_responses/task_N_raw_response.txt` → **原生 API 响应流（逐行）**\n")
            f.write(f"- `output/raw_api_responses/task_N_parsed.json` → 解析后结果\n")
            f.write(f"- `output/results_*.json` → 汇总\n")
            f.write(f"- `logs/` → 完整运行日志\n")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()