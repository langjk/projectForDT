from PyQt5.QtCore import QThread, pyqtSignal
import queue
import threading

class SerialManagerThread(QThread):
    result_signal = pyqtSignal(str)  # 信号，用于传递结果到主线程

    def __init__(self, serial_manager):
        super().__init__()
        self.serial_manager = serial_manager  # 使用统一的串口管理器
        self.task_queue = queue.Queue()  # 任务队列
        self.running = True

    def run(self):
        while self.running:
            try:
                task = self.task_queue.get(timeout=1)
                if task:
                    command, callback = task
                    print(f"收到任务: {command}")
                    if command[0] == "connect":
                        port = command[1]
                        with self.serial_manager.lock:
                            success = self.serial_manager.connect(port)
                        if callback:
                            callback(success)
                        print(f"连接任务完成: {port}, 状态: {'成功' if success else '失败'}")
                    elif command == "disconnect":
                        with self.serial_manager.lock:
                            success = self.serial_manager.disconnect()
                        if callback:
                            callback(success)
                        print(f"断开任务完成, 状态: {'成功' if success else '失败'}")
                    else:
                        with self.serial_manager.lock:
                            response = self.serial_manager.send_data(command)
                        if callback:
                            callback(response)
            except queue.Empty:
                continue
            except Exception as e:
                self.result_signal.emit(f"串口线程错误: {str(e)}")

    def add_task(self, command, callback=None):
        """将任务添加到队列"""
        self.task_queue.put((command, callback))

    def stop(self):
        """停止线程"""
        self.running = False
        self.wait()
