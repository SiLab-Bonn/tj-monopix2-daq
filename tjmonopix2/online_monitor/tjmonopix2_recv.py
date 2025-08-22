import time
import numpy as np

from PyQt5 import QtWidgets
import pyqtgraph as pg
from pyqtgraph.dockarea import DockArea, Dock

from online_monitor.utils import utils
from online_monitor.receiver.receiver import Receiver


class TJMonopix2(Receiver):

    def setup_receiver(self):
        self.occupancy_data = None
        self.tot_data = None
        self.tdc_data = None
        # We want to change converter settings
        self.set_bidirectional_communication()

    def setup_widgets(self, parent, name):
        dock_area = DockArea()
        parent.addTab(dock_area, name)

        # Docks
        dock_occcupancy = Dock("Occupancy", size=(400, 400))
        dock_tot = Dock("Time over threshold values (TOT)", size=(400, 400))
        dock_tdc = Dock("TDC", size=(400, 400))
        dock_status = Dock("Status", size=(800, 40))
        dock_area.addDock(dock_occcupancy, 'left')
        dock_area.addDock(dock_tot, 'right', dock_occcupancy)
        dock_area.addDock(dock_tdc, 'bottom', dock_tot)
        dock_area.addDock(dock_status, 'top')

        # Status dock on top
        cw = QtWidgets.QWidget()
        cw.setStyleSheet("QWidget {background-color:white}")
        layout = QtWidgets.QGridLayout()
        cw.setLayout(layout)
        self.rate_label = QtWidgets.QLabel("Readout Rate\n0 Hz")
        self.hit_rate_label = QtWidgets.QLabel("Hit Rate\n0 Hz")
        self.trigger_rate_label = QtWidgets.QLabel("Trigger Rate\n0 Hz")
        self.timestamp_label = QtWidgets.QLabel("Data Timestamp\n")
        self.plot_delay_label = QtWidgets.QLabel("Plot Delay\n")
        self.scan_parameter_label = QtWidgets.QLabel("Parameter ID\n")
        self.spin_box = QtWidgets.QSpinBox(value=0)
        self.spin_box.setMaximum(1000000)
        self.spin_box.setSuffix(" Readouts")
        self.reset_button = QtWidgets.QPushButton('Reset')
        self.noisy_checkbox = QtWidgets.QCheckBox('Mask noisy pixels')
        layout.addWidget(self.timestamp_label, 0, 0, 0, 1)
        layout.addWidget(self.plot_delay_label, 0, 1, 0, 1)
        layout.addWidget(self.rate_label, 0, 2, 0, 1)
        layout.addWidget(self.hit_rate_label, 0, 3, 0, 1)
        layout.addWidget(self.trigger_rate_label, 0, 4, 0, 1)
        layout.addWidget(self.scan_parameter_label, 0, 5, 0, 1)
        layout.addWidget(self.spin_box, 0, 6, 0, 1)
        layout.addWidget(self.noisy_checkbox, 0, 7, 0, 1)
        layout.addWidget(self.reset_button, 0, 8, 0, 1)
        dock_status.addWidget(cw)

        # Connect widgets
        self.reset_button.clicked.connect(lambda: self.send_command('RESET'))
        self.spin_box.valueChanged.connect(lambda value: self.send_command(str(value)))
        self.noisy_checkbox.stateChanged.connect(lambda value: self.send_command('MASK %d' % value))

        # Different plot docks
        occupancy_graphics = pg.GraphicsLayoutWidget()
        occupancy_graphics.show()
        view = occupancy_graphics.addViewBox()
        self.occupancy_img = pg.ImageItem(border='w')
        # Set colormap from matplotlib
        lut = utils.lut_from_colormap("plasma")

        self.occupancy_img.setLookupTable(lut, update=True)
        plot = pg.PlotWidget(viewBox=view, labels={'bottom': 'Column', 'left': 'Row'})
        plot.addItem(self.occupancy_img)

        dock_occcupancy.addWidget(plot)

        tot_plot_widget = pg.PlotWidget(background="w")
        self.tot_plot = tot_plot_widget.plot(np.linspace(-0.5, 15.5, 17),
                                             np.zeros((16)), stepMode=True)
        tot_plot_widget.showGrid(y=True)
        dock_tot.addWidget(tot_plot_widget)

        tdc_widget = pg.PlotWidget()
        self.tdc_plot = tdc_widget.plot(np.linspace(-0.5, 500 - 0.5, 500 + 1),
                                        np.zeros((500)), stepMode=True)
        tdc_widget.showGrid(y=True)
        dock_tdc.addWidget(tdc_widget)

        self.plot_delay = 0

    def deserialize_data(self, data):
        return utils.simple_dec(data)[1]

    def _update_rate(self, fps, hps, tps, recent_total_hits, recent_trigger_words):
        self.rate_label.setText("Readout Rate\n%d Hz" % fps)
        if self.spin_box.value() == 0:  # show number of hits, all hits are integrated
            self.hit_rate_label.setText("Total Hits\n%d" % int(recent_total_hits))
            self.trigger_rate_label.setText("Total triggers\n%d" % int(recent_trigger_words))
        else:
            self.hit_rate_label.setText("Hit Rate\n%d Hz" % int(hps))
            self.trigger_rate_label.setText("Trigger Rate\n%d Hz" % int(tps))

    def handle_data(self, data):
        # Histogram data
        self.occupancy_data = data['occupancy']
        self.tot_data = data['tot_hist']
        self.tdc_data = data['tdc_hist']

        # Meta data
        self._update_rate(data['meta_data']['fps'],
                          data['meta_data']['hps'],
                          data['meta_data']['tps'],
                          data['meta_data']['total_hits'],
                          data['meta_data']['total_triggers'])

        self.timestamp_label.setText("Data Timestamp\n%s" % time.asctime(time.localtime(data['meta_data']['timestamp_stop'])))
        self.scan_parameter_label.setText("Parameter ID\n%d" % data['meta_data']['scan_param_id'])
        now = time.time()
        self.plot_delay = self.plot_delay * 0.9 + (now - data['meta_data']['timestamp_stop']) * 0.1
        self.plot_delay_label.setText("Plot Delay\n%s" % 'not realtime' if abs(self.plot_delay) > 5 else "Plot Delay\n%1.2f ms" % (self.plot_delay * 1.e3))

    def refresh_data(self):

        if self.occupancy_data is not None:
            self.occupancy_img.setImage(self.occupancy_data[:, :], autoDownSample=True)
        if self.tot_data is not None:
            self.tot_plot.setData(x=np.arange(-0.5, 128.5, 1),
                                  y=self.tot_data, fillLevel=0,
                                  brush=(0, 0, 255, 150))
        if self.tdc_data is not None:
            self.tdc_plot.setData(x=np.linspace(-0.5, self.tdc_data.shape[0] - 0.5, self.tdc_data.shape[0] + 1),
                                  y=self.tdc_data,
                                  # stepMode=True,
                                  fillLevel=0,
                                  brush=(0, 0, 255, 150))
