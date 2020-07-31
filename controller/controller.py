import json
import time

import wx
import socket


DEFAULT_SHIP_ADDR = "USS-Lux.local"
DEFAULT_SHIP_PORT = 3141

ID_CONNECT = 10001
ID_CABINS = 10002
ID_CABINS_MODE = 10003
ID_NACELLES = 10004
ID_NACELLES_MODE = 10005
ID_BLINKERS = 10006


class ControlPanel(wx.Panel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        main_sizer = wx.GridBagSizer(5, 5)

        self.cabins = wx.CheckBox(self, id=ID_CABINS, label="Cabins")
        self.cabins_mode = wx.RadioBox(self, id=ID_CABINS_MODE, choices=("Random", "Static"))

        self.nacelles = wx.CheckBox(self, id=ID_NACELLES, label="Nacelles")
        self.nacelles_mode = wx.RadioBox(self, id=ID_NACELLES_MODE, choices=("Pulse", "Static"))

        self.blinkers = wx.CheckBox(self, id=ID_BLINKERS, label="Blinkers")

        main_sizer.Add(
            self.cabins,
            pos=(0, 0)
        )
        main_sizer.Add(
            self.cabins_mode,
            pos=(1, 0)
        )
        main_sizer.Add(
            self.nacelles,
            pos=(0, 2)
        )
        main_sizer.Add(
            self.nacelles_mode,
            pos=(1, 2)
        )
        main_sizer.Add(
            self.blinkers,
            pos=(0, 4)
        )

        main_sizer.AddGrowableCol(1)
        main_sizer.AddGrowableCol(3)
        self.SetSizer(main_sizer)

    def set_state(self, state):
        if type(state) is not dict:
            raise TypeError("Non-dict state given.")
        self.cabins.SetValue(state["cabins"])
        self.cabins_mode.SetSelection(
            [self.cabins_mode.GetItemLabel(i).lower() for i in range(self.cabins_mode.GetCount())].index(state["cabins_mode"])
        )
        self.nacelles.SetValue(state["nacelles"])
        self.nacelles_mode.SetSelection(
            [self.nacelles_mode.GetItemLabel(i).lower() for i in range(self.nacelles_mode.GetCount())].index(
                state["nacelles_mode"])
        )
        self.blinkers.SetValue(state["blinkers"])

    def Enable(self, enable=True):
        super(ControlPanel, self).Enable(enable)
        self.cabins_mode.Enable(enable)
        self.nacelles_mode.Enable(enable)

    def Disable(self):
        self.Enable(False)


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
        self.Bind(wx.EVT_CHECKBOX, self.state_change)
        self.Bind(wx.EVT_RADIOBOX, self.mode_change)

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
                self.refresh_state()
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
        self.control_panel.set_state(data)

    def state_change(self, e: wx.Event):
        e_obj: wx.CheckBox = e.GetEventObject()
        command = f"{e_obj.GetLabel().lower()} {'on' if e_obj.GetValue() else 'off'}"
        print(command)
        resp = self.send_command(command)

    def mode_change(self, e: wx.Event):
        e_obj: wx.RadioBox = e.GetEventObject()
        if e_obj.GetId() == ID_CABINS_MODE:
            target = "cabins"
        elif e_obj.GetId() == ID_NACELLES_MODE:
            target = "nacelles"
        else:
            return
        command = f"{target} mode {e_obj.GetItemLabel(e_obj.GetSelection()).lower()}"
        print(command)
        resp = self.send_command(command)



if __name__ == '__main__':
    app = Controller()
    app.MainLoop()
