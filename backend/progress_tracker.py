"""
进度追踪模块
支持训练和视频生成的实时进度监控
"""
import re
import time
import threading
from collections import deque

class ProgressTracker:
    """进度追踪器"""
    
    def __init__(self):
        self.tasks = {}  # 任务字典: {task_id: task_info}
        self.lock = threading.Lock()
        
    def create_task(self, task_id, task_type, total_steps=None):
        """创建新任务"""
        with self.lock:
            self.tasks[task_id] = {
                'type': task_type,  # 'train' or 'generate'
                'status': 'running',
                'progress': 0,
                'current_step': 0,
                'total_steps': total_steps,
                'message': '初始化中...',
                'start_time': time.time(),
                'logs': deque(maxlen=50),  # 最近50条日志
                'details': {}
            }
    
    def update_progress(self, task_id, current_step=None, message=None, details=None):
        """更新任务进度"""
        with self.lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            
            if current_step is not None:
                task['current_step'] = current_step
                if task['total_steps']:
                    task['progress'] = min(100, int(current_step / task['total_steps'] * 100))
            
            if message:
                task['message'] = message
                task['logs'].append({
                    'time': time.time(),
                    'message': message
                })
            
            if details:
                task['details'].update(details)
    
    def complete_task(self, task_id, success=True, message=None):
        """完成任务"""
        with self.lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task['status'] = 'completed' if success else 'failed'
            task['progress'] = 100 if success else task['progress']
            if message:
                task['message'] = message
            task['end_time'] = time.time()
    
    def get_task_info(self, task_id):
        """获取任务信息"""
        with self.lock:
            return self.tasks.get(task_id, None)
    
    def parse_train_log(self, task_id, log_line):
        """解析训练日志"""
        # 匹配格式: step: 100, global_step: 100, epoch: 1, ... loss: 0.12345
        step_match = re.search(r'step:\s*(\d+)', log_line)
        global_step_match = re.search(r'global_step:\s*(\d+)', log_line)
        epoch_match = re.search(r'epoch:\s*(\d+)', log_line)
        loss_match = re.search(r'total loss:\s*([\d.]+)', log_line)
        
        if step_match or global_step_match:
            current_step = int(global_step_match.group(1)) if global_step_match else int(step_match.group(1))
            
            details = {}
            if epoch_match:
                details['epoch'] = int(epoch_match.group(1))
            if loss_match:
                details['loss'] = float(loss_match.group(1))
            
            message = f"训练中: Step {current_step}"
            if epoch_match:
                message += f", Epoch {details['epoch']}"
            if loss_match:
                message += f", Loss {details['loss']:.4f}"
            
            self.update_progress(task_id, current_step, message, details)
    
    def parse_generate_log(self, task_id, log_line):
        """解析视频生成日志"""
        # 匹配常见的进度模式
        patterns = [
            r'Processing frame (\d+)/(\d+)',
            r'Frame (\d+) of (\d+)',
            r'(\d+)/(\d+) frames',
            r'Progress:\s*(\d+)%',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_line, re.IGNORECASE)
            if match:
                if '%' in pattern:
                    progress = int(match.group(1))
                    self.update_progress(task_id, message=f"生成中: {progress}%")
                else:
                    current = int(match.group(1))
                    total = int(match.group(2))
                    
                    task = self.get_task_info(task_id)
                    if task and not task['total_steps']:
                        task['total_steps'] = total
                    
                    self.update_progress(
                        task_id, 
                        current, 
                        f"生成中: {current}/{total} 帧"
                    )
                return
        
        # 如果没有明确进度，根据关键词估算
        if 'start' in log_line.lower() or '开始' in log_line:
            self.update_progress(task_id, message='开始生成...')
        elif 'finish' in log_line.lower() or '完成' in log_line:
            self.complete_task(task_id, True, '生成完成')
        elif 'error' in log_line.lower() or '错误' in log_line:
            self.complete_task(task_id, False, '生成失败')

# 全局实例
tracker = ProgressTracker()
