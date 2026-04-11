# src/utils/logger.py
import sys
import os
import logging
import io
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from threading import Lock
import time

class _PrintToLog(io.TextIOBase):
    """将 print() 输出安全重定向到 logging"""
    def __init__(self, logger, level=logging.INFO):
        super().__init__()
        self.logger = logger
        self.level = level
        self._buffer = ""
        self._lock = Lock()  # 多线程安全

    def write(self, text):
        with self._lock:
            self._buffer += text
            while "\n" in self._buffer:
                line, self._buffer = self._buffer.split("\n", 1)
                if line.strip():
                    self.logger.log(self.level, line)

    def flush(self):
        with self._lock:
            if self._buffer.strip():
                self.logger.log(self.level, self._buffer)
                self._buffer = ""

def setup_production_logger(log_dir: str = "logs", max_bytes: int = 5 * 1024 * 1024, backup_count: int = 3):
    """初始化日志系统并拦截 print()"""
    # 📦 打包后路径自适应
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录

    log_dir = os.path.join(base_dir, log_dir)
    os.makedirs(log_dir, exist_ok=True)
    
    # 按天分文件，避免单文件过大
    today = datetime.now().strftime('%Y%m%d')
    log_file = os.path.join(log_dir, f"d2r_monitor_{today}.log")

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # 清除现有的处理器，避免重复添加
    root_logger.handlers.clear()

    # 统一格式：时间 [级别] 模块: 消息
    fmt = logging.Formatter(
        "%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 📁 文件处理器（按天轮转）
    try:
        # 使用TimedRotatingFileHandler按天轮转
        file_handler = TimedRotatingFileHandler(
            log_file, 
            when='midnight',  # 每天午夜轮转
            interval=1, 
            backupCount=backup_count, 
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        file_handler.suffix = "%Y%m%d.log"
        
        # 添加额外的旋转日志处理器，按文件大小轮转
        size_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count, 
            encoding="utf-8"
        )
        size_handler.setLevel(logging.DEBUG)
        size_handler.setFormatter(fmt)
    except Exception as e:
        print(f"❌ 创建日志文件处理器失败: {e}")
        # 回退到基本的文件处理器
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        size_handler = None

    # 🖥️ 控制台处理器（仅显示 INFO 及以上，保持终端清爽）
    console_handler = logging.StreamHandler(sys.__stdout__)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)

    # 🔁 避免重复添加（热重载/多次调用时安全）
    root_logger.addHandler(file_handler)
    if size_handler:
        root_logger.addHandler(size_handler)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("PyQt5").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("torch").setLevel(logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.INFO)

    # 🔁 重定向 print() 到日志（保留原有代码零修改）
    sys.stdout = _PrintToLog(root_logger, logging.INFO)
    sys.stderr = _PrintToLog(root_logger, logging.ERROR)

    # 🌪️ 同步拦截未捕获异常到日志
    original_excepthook = sys.excepthook
    def _logged_excepthook(exc_type, exc_value, exc_traceback):
        root_logger.error("未捕获异常", exc_info=(exc_type, exc_value, exc_traceback))
        original_excepthook(exc_type, exc_value, exc_traceback)
    sys.excepthook = _logged_excepthook

    # 记录日志系统启动信息
    root_logger.info("=" * 60)
    root_logger.info("日志系统已启动")
    root_logger.info(f"日志文件: {log_file}")
    root_logger.info(f"日志目录: {log_dir}")
    root_logger.info(f"备份数量: {backup_count}")
    root_logger.info("=" * 60)
    
    return root_logger


def get_logger(name: str):
    """获取指定名称的日志器"""
    return logging.getLogger(name)


# 方便使用的快捷函数
def debug(msg, *args, **kwargs):
    """调试级别日志"""
    logging.debug(msg, *args, **kwargs)

def info(msg, *args, **kwargs):
    """信息级别日志"""
    logging.info(msg, *args, **kwargs)

def warning(msg, *args, **kwargs):
    """警告级别日志"""
    logging.warning(msg, *args, **kwargs)

def error(msg, *args, **kwargs):
    """错误级别日志"""
    logging.error(msg, *args, **kwargs)

def critical(msg, *args, **kwargs):
    """严重级别日志"""
    logging.critical(msg, *args, **kwargs)