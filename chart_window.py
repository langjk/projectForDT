from PyQt5.QtChart import QChart, QChartView, QLineSeries
from PyQt5.QtWidgets import QVBoxLayout, QWidget, QComboBox, QLabel


class ChartWidget(QWidget):
    """
    折线图显示模块
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("折线图")
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.device_selector = QComboBox()
        self.device_selector.currentIndexChanged.connect(self.change_device)
        self.layout.addWidget(self.device_selector)

        self.chart = QChart()
        self.chart.setTitle("实时数据")
        self.set_series = QLineSeries()
        self.set_series.setName("设定流量(%)")
        self.display_series = QLineSeries()
        self.display_series.setName("显示流量(%)")
        self.chart.addSeries(self.set_series)
        self.chart.addSeries(self.display_series)

        # 设置图表坐标轴
        self.chart.createDefaultAxes()
        self.chart.axisX().setTitleText("时间")
        self.chart.axisY().setTitleText("百分比")

        self.chart_view = QChartView(self.chart)
        self.layout.addWidget(self.chart_view)

        self.device_data = {}

    def add_device(self, address):
        """
        添加新设备到选择器
        """
        self.device_selector.addItem(f"设备 {address:02X}")
        self.device_data[address] = {"set_flow": [], "display_flow": []}

    def update_chart(self, address, set_flow, display_flow):
        """
        更新指定设备的折线图
        """
        if address in self.device_data:
            data = self.device_data[address]
            data["set_flow"].append(set_flow)
            data["display_flow"].append(display_flow)

            # 限制显示点数
            if len(data["set_flow"]) > 50:
                data["set_flow"].pop(0)
                data["display_flow"].pop(0)

            # 更新图表
            if self.device_selector.currentText() == f"设备 {address:02X}":
                self.set_series.clear()
                self.display_series.clear()
                for i, (s, d) in enumerate(zip(data["set_flow"], data["display_flow"])):
                    self.set_series.append(i, s)
                    self.display_series.append(i, d)

    def change_device(self):
        """
        切换设备时更新图表
        """
        current_text = self.device_selector.currentText()
        if current_text.startswith("设备 "):
            address = int(current_text.split()[1], 16)
            if address in self.device_data:
                self.update_chart(address, 0, 0)
