import json
import time

import wx
import socket


DEFAULT_SHIP_ADDR = "pipin.local"
DEFAULT_SHIP_PORT = 3141

ID_CONNECT = 10001


class ShipState:
    def __init__(self):
        self.cabins = True
        self.dynamic_cabins = True
        self.nacelles = True
        self.nacelles_pulse = True
        self.blinkers = True


class ControlPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        main_sizer = wx.GridBagSizer(5, 5)

        self.cabins = wx.CheckBox(self)
        self.dynamic_cabins = wx.CheckBox(self)

        self.nacelles = wx.CheckBox(self)
        self.nacelles_pulse = wx.CheckBox(self)

        self.blinkers = wx.CheckBox(self)

        main_sizer.Add(
            wx.StaticText(self, label="Cabins:"),
            pos=(0, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        main_sizer.Add(
            self.cabins,
            pos=(0, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )

        main_sizer.Add(
            wx.StaticText(self, label="Cabins Mode:"),
            pos=(1, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        main_sizer.Add(
            self.dynamic_cabins,
            pos=(1, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )

        main_sizer.Add(
            width=0,
            height=0,
            pos=(2, 0)
        )

        main_sizer.Add(
            wx.StaticText(self, label="Nacelles:"),
            pos=(3, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        main_sizer.Add(
            self.nacelles,
            pos=(3, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )

        main_sizer.Add(
            wx.StaticText(self, label="Nacelles Pulse:"),
            pos=(4, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        main_sizer.Add(
            self.nacelles_pulse,
            pos=(4, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )

        main_sizer.Add(
            width=0,
            height=0,
            pos=(5, 0)
        )

        main_sizer.Add(
            wx.StaticText(self, label="Blinkers:"),
            pos=(6, 0),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_RIGHT
        )
        main_sizer.Add(
            self.blinkers,
            pos=(6, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALIGN_LEFT
        )

        main_sizer.AddGrowableCol(0, 1)
        main_sizer.AddGrowableCol(1, 1)
        self.SetSizer(main_sizer)


class Controller(wx.App):
    def __init__(self, redirect=False, filename=None):
        wx.App.__init__(self, redirect, filename)
        self.main_frame = wx.Frame(
            None,
            wx.ID_ANY,
            title="USS Lux - Boldly Lighting",
            style=wx.DEFAULT_FRAME_STYLE | wx.RESIZE_BORDER
        )
        self.main_frame.SetBackgroundColour((255, 255, 255))

        self.target_addr = DEFAULT_SHIP_ADDR
        self.target_port = DEFAULT_SHIP_PORT

        self.socket: socket.socket = socket.socket()
        self.connected = False

        connection_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.host_box = wx.TextCtrl(
            self.main_frame,
            size=(100, -1)
        )
        self.host_box.SetValue(DEFAULT_SHIP_ADDR)
        self.port_box = wx.TextCtrl(
            self.main_frame,
            size=(50, -1)
        )
        self.port_box.SetValue(str(DEFAULT_SHIP_PORT))
        connection_sizer.Add(
            wx.StaticText(
                self.main_frame,
                label="Host:"
            ),
            0,
            wx.EXPAND | wx.RIGHT,
            5
        )
        connection_sizer.Add(
            self.host_box,
            2,
            wx.EXPAND | wx.RIGHT,
            5
        )
        connection_sizer.Add(
            wx.StaticText(
                self.main_frame,
                label="Port:"
            ),
            0,
            wx.EXPAND | wx.RIGHT,
            5
        )
        connection_sizer.Add(
            self.port_box,
            1,
            wx.EXPAND | wx.RIGHT,
            5
        )
        connection_sizer.Add(
            wx.Button(
                parent=self.main_frame,
                id=ID_CONNECT,
                label="Connect"
            ),
            0,
            wx.EXPAND
        )

        self.connection_label = wx.StaticText(
            self.main_frame,
            label="Not Connected"
        )

        self.control_panel = ControlPanel(self.main_frame)
        self.control_panel.Disable()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        main_sizer.Add(
            connection_sizer,
            0,
            wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
            10
        )
        main_sizer.AddStretchSpacer(1)
        main_sizer.Add(
            self.connection_label,
            0,
            wx.TOP | wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL,
            10
        )
        main_sizer.AddStretchSpacer(1)
        main_sizer.Add(
            self.control_panel,
            0,
            wx.EXPAND | wx.ALL,
            10
        )
        main_sizer.AddStretchSpacer(1)

        self.main_frame.SetSizerAndFit(main_sizer)

        self.Bind(wx.EVT_BUTTON, self.open_connection, id=ID_CONNECT)

        self.main_frame.Show()

    def open_connection(self, e=None):
        if not self.connected:
            try:
                self.connection_label.SetLabel("Connecting...")
                self.socket.connect((self.host_box.GetValue(), int(self.port_box.GetValue())))
                self.connected = True
                self.connection_label.SetLabel("Connected")
                self.connection_label.SetForegroundColour((0, 255, 0))
                self.control_panel.Enable()
            except ConnectionRefusedError:
                self.connection_label.SetLabel("Host Refused Connection")
                self.connection_label.SetForegroundColour((255, 0, 0))
            except socket.gaierror:
                self.connection_label.SetLabel("Could Not Resolve Host")
                self.connection_label.SetForegroundColour((255, 0, 0))
            self.main_frame.Layout()

    def send_command(self, command):
        if self.connected is False:
            return
        data = json.dumps(command).encode() + b"\n"
        try:
            self.socket.send(data)
            resp = self.socket.recv(512)
            resp = json.loads(resp.decode())
            return resp
        except (ConnectionError, OSError):
            self.connected = False
            self.control_panel.Disable()
            self.open_connection()

    def refresh_state(self, e=None):
        data = self.send_command("get_state")



if __name__ == '__main__':
    app = Controller()
    app.MainLoop()
