import os
# 关键：在导入torch前设置这个环境变量
os.environ['TORCH_FORCE_WEIGHTS_ONLY_LOAD'] = '0'

import torch
from ultralytics import YOLO

# 添加YOLO的分类模型到安全全局列表
from ultralytics.nn.tasks import ClassificationModel
torch.serialization.add_safe_globals([ClassificationModel])

print("✅ PyTorch版本:", torch.__version__)
print("✅ CUDA可用:", torch.cuda.is_available())

# 测试加载模型
try:
    model = YOLO('yolov8n-cls.pt')
    print("✅ YOLOv8分类模型加载成功")
except Exception as e:
    print(f"❌ 加载失败: {e}")