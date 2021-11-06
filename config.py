import yaml
import os
import logging

def loadConfig(logging: logging) -> dict:
    # 加载本地配置
    if os.path.exists('config.local.yaml'):
        return yaml.full_load(open('config.local.yaml', 'r'))
    elif os.path.exists('config.yaml'):
        return yaml.full_load(open('config.yaml', 'r'))
    else:
        logging.error("未找到config.yaml配置文件, 请确认.")
        os._exit(1)