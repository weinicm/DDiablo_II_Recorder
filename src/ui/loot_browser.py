# src/ui/loot_browser.py
import os
import json
from pathlib import Path
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class LootBrowser(QMainWindow):
    """内置Loot文件浏览器 - 跟随主题配色"""
    
    def __init__(self, loot_dir="./Loot", parent=None):
        super().__init__(parent)
        self.loot_dir = Path(loot_dir)
        self.loot_dir.mkdir(parents=True, exist_ok=True)
        
        # 当前显示的图片路径
        self.current_image_path = None
        # 文件数据缓存
        self.files_cache = {}
        # 原始图片
        self.original_pixmap = None
        
        self._init_ui()
        self._apply_theme()  # 应用主题，但不加载图片
        
    def _init_ui(self):
        """初始化UI - 左侧2列表格"""
        self.setWindowTitle("Loot文件浏览器")
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(1000, 700)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # === 左侧面板 - 固定宽度，2列文件列表 ===
        left_panel = QWidget()
        left_panel.setObjectName("leftPanel")
        left_panel.setFixedWidth(320)  # 固定宽度，确保显示2列
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        
        # 搜索框
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setObjectName("settings_input")  # 使用主题样式
        self.search_input.setPlaceholderText("搜索文件名...")
        self.search_input.textChanged.connect(self._filter_images)
        self.search_input.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)
        
        # 工具栏
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        
        # 刷新按钮
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setObjectName("btn_refresh")
        self.btn_refresh.setFixedSize(30, 30)
        self.btn_refresh.setToolTip("刷新列表")
        self.btn_refresh.clicked.connect(self._load_images)
        toolbar_layout.addWidget(self.btn_refresh)
        
        toolbar_layout.addStretch()
        left_layout.addWidget(toolbar)
        
        # 创建QTableWidget来显示文件列表（2列）
        self.table_widget = QTableWidget()
        self.table_widget.setObjectName("tableWidget")
        self.table_widget.setColumnCount(2)  # 设置为2列
        self.table_widget.setHorizontalHeaderLabels(["", "文件名"])
        self.table_widget.horizontalHeader().setStretchLastSection(True)  # 让最后一列填充剩余空间
        self.table_widget.horizontalHeader().setVisible(False)  # 隐藏表头
        self.table_widget.verticalHeader().setVisible(False)  # 隐藏行号
        self.table_widget.setShowGrid(False)  # 隐藏网格线
        self.table_widget.setAlternatingRowColors(True)  # 交替行颜色
        self.table_widget.setSelectionBehavior(QTableWidget.SelectRows)  # 整行选择
        self.table_widget.setSelectionMode(QTableWidget.SingleSelection)  # 单选模式
        self.table_widget.setEditTriggers(QTableWidget.NoEditTriggers)  # 禁止编辑
        self.table_widget.setVerticalScrollMode(QTableWidget.ScrollPerPixel)  # 平滑滚动
        
        # 设置列宽
        self.table_widget.setColumnWidth(0, 60)  # 第1列：缩略图，固定60像素
        self.table_widget.setColumnWidth(1, 240)  # 第2列：文件名，240像素
        
        # 连接信号
        self.table_widget.itemDoubleClicked.connect(self._on_image_double_clicked)
        self.table_widget.itemSelectionChanged.connect(self._on_table_selection_changed)
        
        left_layout.addWidget(self.table_widget, 1)  # 让表格占据所有可用空间
        
        # 删除按钮
        self.btn_delete = QPushButton("🗑️ 删除文件")
        self.btn_delete.setObjectName("btn_del")  # 使用主题样式
        self.btn_delete.clicked.connect(self._delete_selected)
        self.btn_delete.setMinimumHeight(35)
        left_layout.addWidget(self.btn_delete)
        
        # === 右侧面板 - 图片预览区域 ===
        right_panel = QWidget()
        right_panel.setObjectName("rightPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        # 图片预览容器
        self.preview_container = QWidget()
        self.preview_container.setObjectName("previewContainer")
        preview_container_layout = QVBoxLayout(self.preview_container)
        preview_container_layout.setContentsMargins(0, 0, 0, 0)
        
        # 滚动区域用于图片
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 图片显示区域
        self.image_label = QLabel("请从左侧选择一张图片")
        self.image_label.setObjectName("imageLabel")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(100, 100)
        self.image_label.setScaledContents(False)  # 禁止自动缩放
        self.scroll_area.setWidget(self.image_label)
        
        preview_container_layout.addWidget(self.scroll_area)
        right_layout.addWidget(self.preview_container)
        
        # 将左右面板添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)  # 右侧面板占据剩余空间
        
        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")
    
    def showEvent(self, event):
        """显示事件，用于窗口居中和自动刷新图片列表"""
        super().showEvent(event)
        self._center_on_screen()
        # 延迟一小段时间，确保窗口显示后再加载，避免界面卡顿
        QTimer.singleShot(100, self._load_images)
    
    def _center_on_screen(self):
        """将窗口居中显示在屏幕中央"""
        # 获取屏幕几何信息
        screen_geometry = QDesktopWidget().screenGeometry()
        
        # 获取窗口几何信息
        window_geometry = self.frameGeometry()
        
        # 计算居中位置
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = (screen_geometry.height() - window_geometry.height()) // 2
        
        # 移动窗口到中心位置
        self.move(x, y)
    
    def _apply_theme(self, theme_name: str = None):
        """应用主题配色"""
        if theme_name is None:
            # 尝试从配置文件获取主题
            try:
                from ...utils.config import load_config
                config = load_config()
                theme_name = config.get("theme", "dark")
            except:
                theme_name = "dark"  # 默认主题
        
        # 获取主题目录
        theme_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "themes")
        base_qss_path = os.path.join(theme_dir, "base_style.qss")
        theme_json_path = os.path.join(theme_dir, f"{theme_name}.json")
        
        if not os.path.exists(base_qss_path) or not os.path.exists(theme_json_path):
            # 如果主题文件不存在，使用内置的简单样式
            self._apply_fallback_style()
            return
        
        try:
            # 加载基本QSS模板
            with open(base_qss_path, "r", encoding="utf-8") as f:
                qss_template = f.read()
            
            # 加载主题颜色
            with open(theme_json_path, "r", encoding="utf-8") as f:
                colors = json.load(f).get("colors", {})
            
            # 替换颜色变量
            for key, value in colors.items():
                qss_template = qss_template.replace(f"{{{{{key}}}}}", value)
            
            # 应用样式
            self.setStyleSheet(qss_template)
            
            # 额外为表格设置交替行颜色
            if "BG" in colors and "INPUT_BG" in colors:
                # 使用主题颜色设置表格样式
                table_style = f"""
                    QTableWidget#tableWidget {{
                        background-color: {colors.get('BG', '#1A1A1A')};
                        border: 1px solid {colors.get('BORDER', '#333333')};
                        border-radius: 3px;
                        color: {colors.get('FG', '#C8C8C8')};
                        font-size: 11px;
                        outline: none;
                        gridline-color: {colors.get('BORDER', '#333333')};
                        alternate-background-color: {colors.get('INPUT_BG', '#262626')};
                    }}
                    
                    QTableWidget#tableWidget::item {{
                        padding: 4px;
                        border: none;
                    }}
                    
                    QTableWidget#tableWidget::item:selected {{
                        background-color: {colors.get('ACCENT', '#4FACFE')};
                        color: #FFFFFF;
                    }}
                    
                    QTableWidget#tableWidget::item:hover {{
                        background-color: {colors.get('BTN_HOVER', '#333333')};
                    }}
                    
                    QHeaderView::section {{
                        background-color: {colors.get('INPUT_BG', '#262626')};
                        border: none;
                        padding: 4px;
                    }}
                    
                    QWidget#leftPanel, QWidget#rightPanel {{
                        background-color: {colors.get('BG', '#1A1A1A')};
                    }}
                    
                    QWidget#previewContainer {{
                        background-color: #1A1A1A;
                    }}
                    
                    QLabel#imageLabel {{
                        background-color: #1A1A1A;
                        border: none;
                        color: {colors.get('FG', '#999999')};
                        font-size: 13px;
                    }}
                    
                    QPushButton#btn_refresh {{
                        padding: 0; margin: 0;
                        min-height: 28px; max-height: 28px;
                        min-width: 28px; max-width: 28px;
                        border-radius: 6px;
                        background: transparent;
                        border: 1px solid transparent;
                        font-size: 16px;
                        font-weight: bold;
                    }}
                    
                    QPushButton#btn_refresh:hover {{
                        background: rgba(255,255,255,0.1);
                        border-color: {colors.get('ACCENT', '#4FACFE')};
                    }}
                    
                    QPushButton#btn_refresh:pressed {{
                        background: rgba(0,0,0,0.2);
                    }}
                """
                # 应用额外样式
                extra_style = f"""
                    {self.styleSheet()}
                    {table_style}
                """
                self.setStyleSheet(extra_style)
            
            print(f"[LootBrowser] ✅ 主题已应用: {theme_name}")
            
        except Exception as e:
            print(f"[LootBrowser] ❌ 应用主题失败: {e}")
            self._apply_fallback_style()
    
    def _apply_fallback_style(self):
        """应用回退样式（当主题文件缺失时）"""
        fallback_style = """
            QMainWindow {
                background-color: #1A1A1A;
            }
            
            QWidget#leftPanel, QWidget#rightPanel {
                background-color: #1A1A1A;
            }
            
            QLineEdit {
                background-color: #262626;
                border: 1px solid #333333;
                border-radius: 3px;
                padding: 6px;
                color: #D0D0D0;
                font-size: 12px;
            }
            
            QLineEdit:focus {
                border: 1px solid #4FACFE;
            }
            
            QPushButton {
                background-color: #2A2A2A;
                border: 1px solid #333333;
                border-radius: 3px;
                color: #B0B0B0;
                font-size: 12px;
                padding: 6px 10px;
            }
            
            QPushButton:hover {
                background-color: #333333;
                border-color: #666666;
            }
            
            QPushButton:pressed {
                background-color: #222222;
            }
            
            QTableWidget#tableWidget {
                background-color: #262626;
                border: 1px solid #333333;
                border-radius: 3px;
                color: #C8C8C8;
                font-size: 11px;
                outline: none;
                gridline-color: #333333;
                alternate-background-color: #2A2A2A;
            }
            
            QTableWidget#tableWidget::item {
                padding: 4px;
                border: none;
            }
            
            QTableWidget#tableWidget::item:selected {
                background-color: #4FACFE;
                color: #FFFFFF;
            }
            
            QTableWidget#tableWidget::item:hover {
                background-color: #333333;
            }
            
            QHeaderView::section {
                background-color: #262626;
                border: none;
                padding: 4px;
            }
            
            QWidget#previewContainer {
                background-color: #1A1A1A;
            }
            
            QLabel#imageLabel {
                background-color: #1A1A1A;
                border: none;
                color: #999999;
                font-size: 13px;
            }
            
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            
            QPushButton#btn_del {
                background-color: #F44336;
                border: 1px solid #d32f2f;
                color: #FFFFFF;
                font-weight: bold;
            }
            
            QPushButton#btn_del:hover {
                background-color: #d32f2f;
            }
            
            QPushButton#btn_del:pressed {
                background-color: #c62828;
            }
            
            QStatusBar {
                background-color: #2C2C2C;
                color: #AAAAAA;
                border-top: 1px solid #444444;
            }
            
            QPushButton#btn_refresh {
                padding: 0; margin: 0;
                min-height: 28px; max-height: 28px;
                min-width: 28px; max-width: 28px;
                border-radius: 6px;
                background: transparent;
                border: 1px solid transparent;
                font-size: 16px;
                font-weight: bold;
            }
            
            QPushButton#btn_refresh:hover {
                background: rgba(255,255,255,0.1);
                border-color: #4FACFE;
            }
            
            QPushButton#btn_refresh:pressed {
                background: rgba(0,0,0,0.2);
            }
        """
        self.setStyleSheet(fallback_style)
    
    def _load_images(self):
        """加载图片文件列表到表格中"""
        # 如果窗口不可见，则不加载
        if not self.isVisible():
            return
            
        self.table_widget.clearContents()
        self.table_widget.setRowCount(0)
        self.files_cache.clear()  # 清空缓存
        
        try:
            # 获取所有图片文件
            image_extensions = ('.png', '.jpg', '.jpeg', '.bmp')
            all_files = []
            
            # 使用列表推导式获取所有文件
            for ext in image_extensions:
                # 获取小写扩展名文件
                lower_ext = f"*{ext}"
                all_files.extend([f for f in self.loot_dir.glob(lower_ext) if f.is_file()])
                
                # 获取大写扩展名文件
                upper_ext = f"*{ext.upper()}"
                all_files.extend([f for f in self.loot_dir.glob(upper_ext) if f.is_file()])
            
            if not all_files:
                self.status_bar.showMessage("文件夹为空")
                return
            
            # 移除重复文件（大小写不敏感）
            unique_files = {}
            for file_path in all_files:
                # 确保文件存在且不是目录
                if file_path.is_file():
                    # 使用绝对路径的字符串表示作为键
                    key = str(file_path.resolve()).lower()
                    unique_files[key] = file_path
            
            # 转换为列表
            image_files = list(unique_files.values())
            
            if not image_files:
                self.status_bar.showMessage("文件夹为空")
                return
            
            # 按修改时间排序（最新的在前）
            image_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # 设置表格行数
            self.table_widget.setRowCount(len(image_files))
            
            # 添加到表格
            for row, img_path in enumerate(image_files):
                try:
                    # 检查文件是否真的存在
                    if not img_path.exists() or not img_path.is_file():
                        continue
                    
                    # 添加到缓存
                    self.files_cache[str(img_path.resolve())] = img_path
                    
                    # 加载缩略图
                    pixmap = QPixmap(str(img_path))
                    
                    if pixmap.isNull():
                        # 如果图片加载失败，使用默认图标
                        icon = self.style().standardIcon(QStyle.SP_FileIcon)
                    else:
                        # 创建缩略图
                        thumbnail = pixmap.scaled(
                            50, 50,  # 缩略图大小
                            Qt.KeepAspectRatio, 
                            Qt.SmoothTransformation
                        )
                        # 创建图标
                        icon = QIcon(thumbnail)
                    
                    # 创建图标项
                    icon_item = QTableWidgetItem()
                    icon_item.setIcon(icon)
                    icon_item.setData(Qt.UserRole, str(img_path))
                    icon_item.setTextAlignment(Qt.AlignCenter)
                    
                    # 设置文件信息
                    file_name = img_path.name
                    stat = img_path.stat()
                    mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%m-%d %H:%M")
                    
                    # 显示信息
                    if len(file_name) > 25:
                        display_name = file_name[:22] + "..."
                    else:
                        display_name = file_name
                    
                    # 创建文件名项
                    name_item = QTableWidgetItem(f"{display_name}\n{mod_time}")
                    name_item.setData(Qt.UserRole, str(img_path))
                    
                    # 工具提示
                    file_size = f"{stat.st_size/1024:.1f}KB"
                    name_item.setToolTip(f"文件名: {file_name}\n大小: {file_size}\n时间: {mod_time}")
                    
                    # 添加到表格
                    self.table_widget.setItem(row, 0, icon_item)
                    self.table_widget.setItem(row, 1, name_item)
                    
                    # 设置行高
                    self.table_widget.setRowHeight(row, 60)
                    
                except Exception as e:
                    print(f"加载图片 {img_path} 失败: {e}")
            
            self.status_bar.showMessage(f"已加载 {len(image_files)} 个图片文件")
            
        except Exception as e:
            self.status_bar.showMessage(f"加载图片列表失败: {e}")
    
    def _filter_images(self, search_text):
        """根据搜索文本过滤图片"""
        search_text = search_text.lower().strip()
        
        for row in range(self.table_widget.rowCount()):
            item = self.table_widget.item(row, 1)  # 获取文件名列的项
            if not item:
                continue
                
            file_path = Path(item.data(Qt.UserRole))
            file_name = file_path.name.lower()
            
            # 显示或隐藏行
            if not search_text or search_text in file_name:
                self.table_widget.setRowHidden(row, False)
            else:
                self.table_widget.setRowHidden(row, True)
    
    def _on_table_selection_changed(self):
        """表格选择变化时预览图片"""
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的行
        selected_row = selected_items[0].row()
        # 获取第一列的项（包含文件路径）
        item = self.table_widget.item(selected_row, 0)
        if not item:
            return
        
        image_path = Path(item.data(Qt.UserRole))
        
        # 检查文件是否存在
        if not image_path.exists():
            self.status_bar.showMessage(f"文件不存在: {image_path.name}")
            # 从缓存中移除
            cache_key = str(image_path.resolve())
            if cache_key in self.files_cache:
                del self.files_cache[cache_key]
            # 重新加载列表
            QTimer.singleShot(100, self._load_images)
            return
        
        try:
            # 加载图片
            pixmap = QPixmap(str(image_path))
            if pixmap.isNull():
                self.image_label.setText("无法加载图片")
                return
            
            # 保存原始图片
            self.original_pixmap = pixmap.copy()
            
            # 延迟一小段时间，确保UI已更新
            QTimer.singleShot(10, self._update_image_preview)
            
            # 显示文件信息在状态栏
            stat = image_path.stat()
            file_size_kb = stat.st_size / 1024
            file_size_mb = stat.st_size / (1024 * 1024)
            mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            
            info_text = (
                f"文件名: {image_path.name} | "
                f"大小: {file_size_kb:.1f}KB ({file_size_mb:.2f}MB) | "
                f"尺寸: {pixmap.width()}x{pixmap.height()} | "
                f"修改时间: {mod_time}"
            )
            
            self.current_image_path = image_path
            self.status_bar.showMessage(info_text)
            
        except Exception as e:
            self.status_bar.showMessage(f"预览图片失败: {e}")
            self.image_label.setText("预览失败")
    
    def resizeEvent(self, event):
        """窗口大小改变事件"""
        super().resizeEvent(event)
        # 延迟一小段时间，确保窗口大小已完全改变
        if self.current_image_path and self.original_pixmap:
            QTimer.singleShot(50, self._update_image_preview)


    def _on_image_double_clicked(self, item):
        """双击表格项用系统默认程序打开"""
        image_path = Path(item.data(Qt.UserRole))
        
        # 检查文件是否存在
        if not image_path.exists():
            self.status_bar.showMessage(f"文件不存在: {image_path.name}")
            # 从缓存中移除
            cache_key = str(image_path.resolve())
            if cache_key in self.files_cache:
                del self.files_cache[cache_key]
            QTimer.singleShot(100, self._load_images)
            return
        
        try:
            if os.name == 'nt':  # Windows
                os.startfile(str(image_path))
            else:  # Linux/macOS
                import subprocess
                subprocess.Popen(['xdg-open', str(image_path)])
            
            self.status_bar.showMessage(f"已用默认程序打开: {image_path.name}")
            
        except Exception as e:
            self.status_bar.showMessage(f"打开图片失败: {e}")
    
    def _update_image_preview(self):
        """更新图片预览 - 根据可用空间智能缩放"""
        if not self.original_pixmap or self.original_pixmap.isNull():
            return
        
        # 获取滚动区域可用空间
        scroll_area_rect = self.scroll_area.viewport().rect()
        if scroll_area_rect.width() <= 0 or scroll_area_rect.height() <= 0:
            return
        
        # 获取图片原始尺寸
        pixmap_width = self.original_pixmap.width()
        pixmap_height = self.original_pixmap.height()
        
        if pixmap_width <= 0 or pixmap_height <= 0:
            return
        
        # 计算可用空间
        available_width = scroll_area_rect.width() - 20  # 减去边距
        available_height = scroll_area_rect.height() - 20
        
        # 如果窗口最大化或全屏，使用滚动区域的实际大小
        if self.isMaximized() or self.windowState() & Qt.WindowFullScreen:
            # 最大化/全屏时，让图片尽可能大
            available_width = scroll_area_rect.width() - 10
            available_height = scroll_area_rect.height() - 10
        
        # 计算缩放比例
        width_ratio = available_width / pixmap_width
        height_ratio = available_height / pixmap_height
        
        # 选择较小的比例，确保图片完全在可见区域内
        scale_factor = min(width_ratio, height_ratio)
        
        # 如果图片本来就小于可用空间，不放大超过原始尺寸
        if scale_factor > 1.0 and pixmap_width < 1920:  # 如果图片不是很大，保持原始尺寸
            new_width = pixmap_width
            new_height = pixmap_height
        else:
            # 计算缩放后的尺寸
            new_width = int(pixmap_width * scale_factor)
            new_height = int(pixmap_height * scale_factor)
        
        # 确保最小尺寸
        if new_width < 100 or new_height < 100:
            new_width = max(100, new_width)
            new_height = max(100, new_height)
        
        # 缩放图片
        scaled_pixmap = self.original_pixmap.scaled(
            new_width, new_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # 设置图片
        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.setFixedSize(scaled_pixmap.size())  # 固定标签大小为图片大小




    def changeEvent(self, event):
        """窗口状态变化事件"""
        if event.type() == QEvent.WindowStateChange:
            if self.isVisible() and self.current_image_path:
                # 延迟一小段时间，确保窗口状态完全改变
                QTimer.singleShot(50, self._update_image_preview)
        super().changeEvent(event)
    
    
    
    def _delete_selected(self):
        """删除选中的文件"""
        selected_items = self.table_widget.selectedItems()
        if not selected_items:
            return
        
        # 获取选中的行
        selected_row = selected_items[0].row()
        # 获取第一列的项（包含文件路径）
        item = self.table_widget.item(selected_row, 0)
        if not item:
            return
        
        image_path = Path(item.data(Qt.UserRole))
        
        # 再次检查文件是否存在
        if not image_path.exists():
            self.status_bar.showMessage(f"文件不存在: {image_path.name}")
            # 从缓存中移除
            cache_key = str(image_path.resolve())
            if cache_key in self.files_cache:
                del self.files_cache[cache_key]
            QTimer.singleShot(100, self._load_images)
            return
        
        # 确认删除
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定要删除文件 {image_path.name} 吗？\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 删除文件
                image_path.unlink()
                
                # 从缓存中移除
                cache_key = str(image_path.resolve())
                if cache_key in self.files_cache:
                    del self.files_cache[cache_key]
                
                # 从表格中移除行
                self.table_widget.removeRow(selected_row)
                
                # 清空预览
                self.image_label.clear()
                self.image_label.setText("请从左侧选择一张图片")
                self.current_image_path = None
                self.original_pixmap = None
                self.image_label.setFixedSize(QSize(100, 100))
                
                self.status_bar.showMessage(f"已删除: {image_path.name}")
                
                # 如果删除后列表为空，显示提示
                if self.table_widget.rowCount() == 0:
                    self.status_bar.showMessage("文件夹为空")
                
            except Exception as e:
                self.status_bar.showMessage(f"删除失败: {e}")
                # 如果删除失败，重新加载列表
                QTimer.singleShot(100, self._load_images)
    
    def closeEvent(self, event):
        """关闭事件"""
        self.current_image_path = None
        self.original_pixmap = None
        self.files_cache.clear()
        super().closeEvent(event)