"""
兼容 chatgpt-on-wechat 的 common.log 模块
让插件可以独立运行
"""
import logging
import sys

# 创建 logger 实例
logger = logging.getLogger("doubao")
logger.setLevel(logging.INFO)

# 如果没有 handler，添加一个
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    logger.addHandler(handler)