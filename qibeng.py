import sys
import serial
import serial.tools.list_ports
import threading
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QTextEdit, QLabel,
    QGroupBox, QHBoxLayout, QLineEdit, QPushButton, QSplitter, QScrollArea
)
from PyQt5.QtChart import QChart, QChartView, QLineSeries, QValueAxis, QDateTimeAxis
from PyQt5.QtCore import QThread, pyqtSignal, Qt
from PyQt5.QtCore import QDateTime

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
    result_signal = pyqtSignal(str)  # 用于传递设备信息
    device_data_signal = pyqtSignal(int, int, int)  # 地址, 设定流量, 显示流量

    def __init__(self, serial_manager, lock):
        super().__init__()
        self.serial_manager = serial_manager  # 保存传递进来的 serial_manager
        self.running = True
        self.lock = lock

    def query_device(self, address):
        """
        查询设备的设定流量和显示流量
        """
        def send_and_receive(data):
            data += calculate_checksum(data)
            with self.lock:
                self.serial_manager.send_data(data)
                response = self.serial_manager.receive_data(7)
            if len(response) == 7 and response[-2:] == calculate_checksum(response[:-2]):
                return int.from_bytes(response[3:5], byteorder='big')
            return None

        set_flow = send_and_receive(bytearray([address, 0x03, 0x00, 0x11, 0x00, 0x01]))
        display_flow = send_and_receive(bytearray([address, 0x03, 0x00, 0x10, 0x00, 0x01]))
        return set_flow, display_flow

    def run(self):
        try:
            online_devices = []

            for address in range(0x00, 0x10):
                if not self.running:
                    break

                # 检查设备是否在线
                data = bytearray([address, 0x03, 0x00, 0x30, 0x00, 0x01])
                data += calculate_checksum(data)
                with self.lock:
                    self.serial_manager.send_data(data)
                    response = self.serial_manager.receive_data(7)
                if len(response) == 7 and response[-2:] == calculate_checksum(response[:-2]):
                    # 设备在线，记录地址
                    online_devices.append(address)

                    # 查询单位和量程
                    unit_data = bytearray([address, 0x01, 0x00, 0x06, 0x00, 0x01])
                    unit_data += calculate_checksum(unit_data)
                    with self.lock:
                        self.serial_manager.send_data(unit_data)
                        unit_response = self.serial_manager.receive_data(7)

                    if len(unit_response) == 6 and unit_response[-2:] == calculate_checksum(unit_response[:-2]):
                        # 解析单位和量程数据
                        unit_code = unit_response[3]  # 单位代码，00=ml/min，01=L/min
                        unit = "ml/min" if unit_code == 0 else "L/min"
                        range_value = int.from_bytes(response[3:5], byteorder='big')  # 量程

                        # 通过信号将信息发送到主线程
                        self.result_signal.emit(f"地址: {address:02X}, 量程: {range_value} {unit}")
                    else:
                        self.result_signal.emit(f"地址: {address:02X} 查询单位失败")

            while self.running:
                for address in online_devices:
                    set_flow, display_flow = self.query_device(address)
                    if set_flow is not None and display_flow is not None:
                        self.device_data_signal.emit(address, set_flow, display_flow)
                self.msleep(300)
        except Exception as e:
            self.result_signal.emit(f"错误1: {str(e)}")


class ModbusScannerApp(QMainWindow):
    device_found_signal = pyqtSignal(str)  # 信号，用于传递设备信息
    def __init__(self, serial_manager):
        super().__init__()
        self.serial_manager = serial_manager
        self.setWindowTitle("ModBus 扫描工具")
        self.resize(1200, 600)

        # 主布局
        main_splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(main_splitter)

        # 左侧布局：设备信息和操作
        left_widget = QWidget()
        self.left_layout = QVBoxLayout()
        left_widget.setLayout(self.left_layout)

        # 初始化滚动区域
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout()
        scroll_widget.setLayout(self.scroll_layout)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        self.left_layout.addWidget(scroll_area)

        scan_button = QPushButton("开始扫描")
        scan_button.clicked.connect(self.start_scan)
        self.left_layout.addWidget(QLabel("选择串口:"))
        self.left_layout.addWidget(scan_button)

        # 扫描结果
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.left_layout.addWidget(self.result_text)

        # 初始化设备小窗字典
        self.device_widgets = {}
        self.lock = threading.Lock()

        # 右侧布局：折线图
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)

        self.chart = QChart()
        self.chart.setTitle("实时数据")
        self.chart_view = QChartView(self.chart)
        right_layout.addWidget(self.chart_view)


        # 创建曲线
        self.set_series = QLineSeries()
        self.set_series.setName("设定流量(%)")  # 设置图例名称

        self.display_series = QLineSeries()
        self.display_series.setName("显示流量(%)")  # 设置图例名称
        
        self.chart.addSeries(self.set_series)
        self.chart.addSeries(self.display_series)

        
        # 创建时间轴作为横坐标
        self.axis_x = QDateTimeAxis()
        self.axis_x.setFormat("HH:mm:ss")  # 时间格式
        self.axis_x.setTitleText("时间")
        self.axis_x.setRange(QDateTime.currentDateTime(), QDateTime.currentDateTime().addSecs(5))  # 初始显示 1 分钟范围
        self.chart.setAxisX(self.axis_x, self.set_series)
        self.chart.setAxisX(self.axis_x, self.display_series)
        self.axis_x.setTickCount(10)

        # 设置纵轴范围
        axis_y = QValueAxis()
        axis_y.setRange(0, 100)  # 0% - 100%
        axis_y.setLabelFormat("%.1f")
        axis_y.setTitleText("百分比")
        self.chart.setAxisY(axis_y, self.set_series)
        self.chart.setAxisY(axis_y, self.display_series)

        # 切换设备选择器
        self.device_selector = QComboBox()
        self.device_selector.currentIndexChanged.connect(self.switch_device)
        right_layout.addWidget(QLabel("切换设备:"))
        right_layout.addWidget(self.device_selector)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        
        main_splitter.setStretchFactor(0, 1)  # 左侧占 1 份
        main_splitter.setStretchFactor(1, 3)  # 右侧占 3 份


    def start_scan(self):
        if not self.serial_manager.get_connection_status():  # 检查是否已连接
            print(self.serial_manager.get_connection_status())
            self.result_text.append("请先连接串口！")
            return

        # 直接调用扫描线程
        self.scan_thread = ModbusScannerThread(self.serial_manager, self.lock)
        self.scan_thread.result_signal.connect(self.display_result)
        self.scan_thread.device_data_signal.connect(self.update_device_data)
        self.scan_thread.start()
    
    def display_result(self, result):
        """
        接收线程信号并更新 UI
        """
        self.result_text.append(result)  # 更新扫描结果
        if "地址" in result and "量程" in result:
            parts = result.split(",")
            address = int(parts[0].split(":")[1].strip(), 16)
            range_value = parts[1].split(":")[1].strip()
            if address not in self.device_widgets:
                self.add_device_widget(address, range_value)

    def add_device_widget(self, address, range_value):
        """
        在主窗口中动态添加设备窗口，并在标题中显示量程
        """
        group_box = QGroupBox(f"设备地址: {address:02X}, 量程: {range_value}")
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

        # 设定流量输入框和按钮
        send_label = QLabel("设定流量:")
        layout.addWidget(send_label)

        send_input = QLineEdit()
        send_input.setPlaceholderText("输入百分比")
        layout.addWidget(send_input)

        send_button = QPushButton("发送")
        send_button.clicked.connect(lambda: self.send_set_flow(address, send_input))
        layout.addWidget(send_button)

        group_box.setLayout(layout)
        self.scroll_layout.addWidget(group_box)

        # 将输入框等控件存储到字典中
        self.device_widgets[address] = {
            "set_flow": set_flow_input,
            "display_flow": display_flow_input,
            "send_input": send_input,
            "send_button": send_button
        }

        # 更新设备选择器
        self.device_selector.addItem(f"设备地址: {address:02X}, 量程: {range_value}")

    def send_set_flow(self, address, input_widget):
        try:
            percentage = float(input_widget.text())
            if not (0 <= percentage <= 100):
                self.result_text.append(f"地址 {address:02X}: 输入百分比无效，应在 0-100 范围内")
                return

            set_value = int((percentage / 100) * 0x0FFF)
            command = bytearray([address, 0x06, 0x00, 0x11]) + set_value.to_bytes(2, byteorder='big') + calculate_checksum(
                bytearray([address, 0x06, 0x00, 0x11]) + set_value.to_bytes(2, byteorder='big'))

            with self.lock:
                self.scan_thread.serial_manager.send_data(command)

            self.result_text.append(f"地址 {address:02X}: 已发送设定流量 {percentage}%")
        except Exception as e:
            self.result_text.append(f"地址 {address:02X}: 发送失败 - {str(e)}")

    def update_device_data(self, address, set_flow, display_flow):
        if address in self.device_widgets:
        # 计算百分比值
            set_flow_percentage = round((set_flow / 0x0FFF) * 100, 2) if 0 <= set_flow <= 0x0FFF else 0.0
            display_flow_percentage = round((display_flow / 0x0FFF) * 100, 2) if 0 <= display_flow <= 0x0FFF else 0.0

            # 更新设备窗口
            self.device_widgets[address]["set_flow"].setText(f"{set_flow_percentage}%")
            self.device_widgets[address]["display_flow"].setText(f"{display_flow_percentage}%")

            # 检查当前选中的设备
            current_device = self.device_selector.currentText()
            if current_device[0:8] == f"设备地址: {address:02X}":
                # 获取当前时间戳
                current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()

                # 更新曲线数据
                self.set_series.append(current_time, set_flow_percentage)
                self.display_series.append(current_time, display_flow_percentage)

                # 动态更新时间范围
                self.axis_x.setRange(
                    QDateTime.fromMSecsSinceEpoch(current_time - 5 * 1000),  # 显示最近 1 分钟数据
                    QDateTime.fromMSecsSinceEpoch(current_time)
                )
                # self.update_chart_axis()

    def update_chart_axis(self):
        """
        更新折线图的横轴范围
        """
        max_points = 50  # 显示的最大点数
        count = max(self.set_series.count(), self.display_series.count())
        min_x = max(0, count - max_points)
        max_x = count

        # 更新横轴范围
        axis_x = self.chart.axisX()
        if not isinstance(axis_x, QValueAxis):
            axis_x = QValueAxis()
            self.chart.setAxisX(axis_x, self.set_series)
            self.chart.setAxisX(axis_x, self.display_series)

        axis_x.setRange(min_x, max_x)
        axis_x.setLabelFormat("%d")
    
    def switch_device(self):
        """
        切换显示设备时，清空当前数据并重置横轴范围
        """
        current_text = self.device_selector.currentText()
        if current_text.startswith("设备地址: "):
            # address = int(current_text.split(":")[1], 16)

            # 清空当前折线图数据
            self.set_series.clear()
            self.display_series.clear()

            # 重置时间范围为当前时间
            current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
            self.axis_x.setRange(
                QDateTime.fromMSecsSinceEpoch(current_time - 5 * 1000),
                QDateTime.fromMSecsSinceEpoch(current_time)
            )

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ModbusScannerApp()
    main_window.show()
    sys.exit(app.exec_())
