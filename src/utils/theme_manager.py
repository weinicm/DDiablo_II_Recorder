import os
from PyQt5.QtWidgets import QApplication

def apply_theme(theme_name: str = "dark"):
    """全局应用 QSS 主题"""
    theme_dir = os.path.join(os.path.dirname(__file__), "..", "themes")
    qss_path = os.path.join(theme_dir, f"{theme_name}.qss")
    
    if not os.path.exists(qss_path):
        qss_path = os.path.join(theme_dir, "dark.qss")  # 兜底默认主题
        
    with open(qss_path, "r", encoding="utf-8") as f:
        qss_content = f.read()
        
    app = QApplication.instance()
    if app:
        app.setStyleSheet(qss_content)
    return qss_path
