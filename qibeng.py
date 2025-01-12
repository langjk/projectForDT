import sys
import serial
import serial.tools.list_ports
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QComboBox, QTextEdit, QLabel, QGroupBox, QHBoxLayout, QLineEdit
)
from PyQt5.QtCore import QThread, pyqtSignal

def calculate_checksum(data):
    """
    计算ModBus RTU CRC16校验和
    """
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder='little')  # ModBus CRC16要求小端序

class ModbusScannerThread(QThread):
    """
    线程：用于扫描地址并实时查询数据
    """
    result_signal = pyqtSignal(str)
    device_data_signal = pyqtSignal(int, int, int)  # 地址, 设定流量, 显示流量
    serial_ready_signal = pyqtSignal(serial.Serial)  # 串口对象共享信号

    def __init__(self, port_name, lock):
        super().__init__()
        self.port_name = port_name
        self.running = True
        self.ser = None
        self.lock = lock  # 串口操作锁

    def query_device(self, address):
        """
        查询设备的设定流量和显示流量
        """
        def send_and_receive(data):
            data += calculate_checksum(data)
            with self.lock:  # 确保串口操作的互斥性
                self.ser.write(data)
                response = self.ser.read(7)
            if len(response) == 7 and response[-2:] == calculate_checksum(response[:-2]):
                return int.from_bytes(response[3:5], byteorder='big')
            return None

        # 查询设定流量
        set_flow = send_and_receive(bytearray([address, 0x03, 0x00, 0x11, 0x00, 0x01]))

        # 查询显示流量
        display_flow = send_and_receive(bytearray([address, 0x03, 0x00, 0x10, 0x00, 0x01]))

        return set_flow, display_flow

    def run(self):
        try:
            self.ser = serial.Serial(self.port_name, 9600, timeout=0.1, write_timeout=0.1)
            self.serial_ready_signal.emit(self.ser)  # 通知主线程串口准备好
            online_devices = []

            # 扫描阶段
            for address in range(0x00, 0x10):
                if not self.running:
                    break

                # 发送数据包
                data = bytearray([address, 0x03, 0x00, 0x30, 0x00, 0x01])
                data += calculate_checksum(data)

                # 确保串口操作互斥
                with self.lock:
                    self.ser.write(data)
                    response = self.ser.read(7)

                if len(response) == 7 and response[-2:] == calculate_checksum(response[:-2]):
                    online_devices.append(address)
                    self.result_signal.emit(f"地址: {address:02X}, 量程: {int.from_bytes(response[3:5], byteorder='big')}")

            # 实时查询阶段
            while self.running:
                for address in online_devices:
                    set_flow, display_flow = self.query_device(address)
                    if set_flow is not None and display_flow is not None:
                        self.device_data_signal.emit(address, set_flow, display_flow)
                self.msleep(1000)  # 每秒查询一次

        except Exception as e:
            self.result_signal.emit(f"错误: {str(e)}")

    def stop(self):
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

class ModbusScannerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ModBus 扫描工具")
        self.resize(600, 400)
        
        # 界面布局
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        layout = QVBoxLayout()
        self.central_widget.setLayout(layout)

        # 串口选择
        self.port_label = QLabel("选择串口:")
        layout.addWidget(self.port_label)

        self.port_combo = QComboBox()
        self.update_ports()
        layout.addWidget(self.port_combo)

        # 扫描按钮
        self.scan_button = QPushButton("开始扫描")
        self.scan_button.clicked.connect(self.start_scan)
        layout.addWidget(self.scan_button)

        # 扫描结果
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)

        # 初始化设备小窗字典
        self.device_widgets = {}
        self.shared_serial = None
        self.lock = threading.Lock()  # 串口访问锁

    def update_ports(self):
        """
        更新可用串口列表
        """
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(port.device)

    def start_scan(self):
        """
        开始扫描
        """
        selected_port = self.port_combo.currentText()
        if not selected_port:
            self.result_text.append("请先选择一个串口！")
            return

        # 启动扫描线程
        self.result_text.append(f"开始扫描串口: {selected_port}")
        self.scan_thread = ModbusScannerThread(selected_port, self.lock)
        self.scan_thread.result_signal.connect(self.display_result)
        self.scan_thread.device_data_signal.connect(self.update_device_data)
        self.scan_thread.serial_ready_signal.connect(self.set_shared_serial)
        self.scan_thread.start()
    def add_device_widget(self, address):
        """
        为在线设备动态增加一个小窗，增加设定流量功能
        """
        group_box = QGroupBox(f"设备地址: {address:02X}")
        layout = QHBoxLayout()

        # 设定流量显示
        set_flow_label = QLabel("设定流量(%)")
        layout.addWidget(set_flow_label)

        set_flow_input = QLineEdit()
        set_flow_input.setReadOnly(True)
        layout.addWidget(set_flow_input)

        # 显示流量显示
        display_flow_label = QLabel("显示流量(%)")
        layout.addWidget(display_flow_label)

        display_flow_input = QLineEdit()
        display_flow_input.setReadOnly(True)
        layout.addWidget(display_flow_input)

        # 添加设定流量输入框和按钮
        send_label = QLabel("设定流量:")
        layout.addWidget(send_label)

        send_input = QLineEdit()
        send_input.setPlaceholderText("输入百分比")
        layout.addWidget(send_input)

        send_button = QPushButton("发送")
        send_button.clicked.connect(lambda: self.send_set_flow(address, send_input))
        layout.addWidget(send_button)

        group_box.setLayout(layout)
        self.central_widget.layout().addWidget(group_box)

        # 存储设备对应的小窗部件
        self.device_widgets[address] = {
            "set_flow": set_flow_input,
            "display_flow": display_flow_input,
            "send_input": send_input,
            "send_button": send_button
        }
    
    def set_shared_serial(self, ser):
        """
        接收共享的串口对象
        """
        self.shared_serial = ser

    def send_set_flow(self, address, input_widget):
        """
        发送设定流量命令
        """
        try:
            if not self.shared_serial or not self.shared_serial.is_open:
                self.result_text.append("串口未打开，无法发送数据")
                return

            # 获取输入的百分比
            percentage = float(input_widget.text())
            if not (0 <= percentage <= 100):
                self.result_text.append(f"地址 {address:02X}: 输入百分比无效，应在 0-100 范围内")
                return

            # 计算设定值 (满度 0x0FFF)
            set_value = int((percentage / 100) * 0x0FFF)
            set_value_bytes = set_value.to_bytes(2, byteorder='big')

            # 构造命令
            command = bytearray([address, 0x06, 0x00, 0x11])
            command.extend(set_value_bytes)
            command.extend(calculate_checksum(command))

            # 使用锁保护串口操作
            with self.lock:
                self.shared_serial.write(command)

            self.result_text.append(f"地址 {address:02X}: 已发送设定流量 {percentage}% (值: {set_value:04X})")
        except ValueError:
            self.result_text.append(f"地址 {address:02X}: 输入百分比格式错误")
        except Exception as e:
            self.result_text.append(f"地址 {address:02X}: 发送失败 - {str(e)}")

    def display_result(self, result):
        """
        显示扫描结果
        """
        if "地址" in result:
            self.result_text.append(result)
            address = int(result.split(":")[1].split(",")[0], 16)
            if address not in self.device_widgets:
                self.add_device_widget(address)

    def update_device_data(self, address, set_flow, display_flow):
        """
        更新设备数据到界面
        """
        if address in self.device_widgets:
            if 0 <= set_flow <= 0x0FFF:
                set_flow_percentage = round((set_flow / 0x0FFF) * 100, 2)
            else:
                set_flow_percentage = 0.0

            if 0 <= display_flow <= 0x0FFF:
                display_flow_percentage = round((display_flow / 0x0FFF) * 100, 2)
            else:
                display_flow_percentage = 0.0

            self.device_widgets[address]["set_flow"].setText(f"{set_flow_percentage}%")
            self.device_widgets[address]["display_flow"].setText(f"{display_flow_percentage}%")

    def closeEvent(self, event):
        """
        窗口关闭时停止线程
        """
        if hasattr(self, "scan_thread") and self.scan_thread.isRunning():
            self.scan_thread.stop()
            self.scan_thread.wait()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ModbusScannerApp()
    main_window.show()
    sys.exit(app.exec_())
