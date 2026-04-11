from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import Qt, pyqtSignal

class DeleteIconLabel(QLabel):
    clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        print("[DeleteIcon] 🟢 实例化")
        self.setFixedSize(22, 22)
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("🗑️")
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WA_Hover, True)
        self._round_id = None
        self._is_hover = False
        self.setVisible(False)
        self._update_style()

    def set_round_id(self, rid):
        print(f"[DeleteIcon] 📥 set_round_id(rid={rid}, type={type(rid)})")
        self._round_id = int(rid) if rid is not None else None
        self.setVisible(self._round_id is not None)
        print(f"[DeleteIcon] 👁️ setVisible({self.isVisible()}), 内部 _round_id={self._round_id}")
        self._update_style()

    def _update_style(self):
        if not self.isVisible():
            self.setStyleSheet("")
            return
        color = "#FF5252" if self._is_hover else "#4A4A4A"
        bg = "background: rgba(255,82,82,0.15);" if self._is_hover else "background: transparent;"
        self.setStyleSheet(f"color: {color}; font-size: 14px; {bg} border-radius: 4px; padding: 0px;")

    def enterEvent(self, event):
        self._is_hover = True; self._update_style(); super().enterEvent(event)
    def leaveEvent(self, event):
        self._is_hover = False; self._update_style(); super().leaveEvent(event)

    def mousePressEvent(self, event):
        print(f"[DeleteIcon] 🖱️ mousePressEvent 触发! button={event.button()}, 当前 _round_id={self._round_id}")
        if event.button() == Qt.LeftButton and self._round_id is not None:
            print(f"[DeleteIcon] 📡 准备发射信号: clicked({self._round_id})")
            self.clicked.emit(self._round_id)
            print(f"[DeleteIcon] ✅ 信号已发射")
        event.accept()
        super().mousePressEvent(event)
