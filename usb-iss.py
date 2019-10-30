from usb_iss import UsbIss, defs
from usb_iss.exceptions import UsbIssError
import sys
import time
import wx
import serial.tools.list_ports;
import threading
import codecs as cdc
import binascii

# USB Iss related global variables
_id = 0
_fwv = 0
_infotext = "COM15: Module ID: {}\nModule FW: {}\nModule Serialnumber: {}\nCurrent Mode: {}"
_ser = 0
_currmode = "UNKNOWN"
_iss = UsbIss()
_stop = 10
_serport = None
wsz = wx.BoxSizer()
_comspeeds = []
_comboboxSpeed = None
_enterKeyPressed = False

class USBISS_Serial_Interface(wx.Frame):

    def __init__(self):
        self._enterKeyPressed = False;
        # Application window
        super().__init__(parent=None,title="USB ISS Serial",size=(650,600))
        self.panel = wx.Panel(self)

        # wx.Timer for updating the received data
        self.updateTimer = wx.Timer(self,wx.ID_ANY)
        self.Bind(wx.EVT_TIMER, self.updateReadDataWindow, self.updateTimer)

        # serial port settings
        self._comspeeds = ["300", "1200", "2400", "9600", "19200", "38400", "57600", "115200", "250000", "1M"]
        self._comboboxSpeed = wx.ComboBox(self.panel,id=wx.ID_ANY,value="speed",choices=list(self._comspeeds))
        self._comboboxSpeed.SetSelection(7)

        #infotext, output and input textboxes
        self.infotext = wx.StaticText(self.panel,id=wx.ID_ANY,label="No device detected.\nSelect COM port\nand connect.")
        self.outputtextlabel = wx.StaticText(self.panel, id=wx.ID_ANY, label="User data for sending:")
        self.outputtext = wx.TextCtrl(self.panel,id=wx.ID_ANY, size=(400,200),style = wx.TE_MULTILINE)
        self.inputtext = wx.TextCtrl(self.panel,id=wx.ID_ANY, size=(400,200),style = wx.TE_MULTILINE)
        self.inputtextlabel = wx.StaticText(self.panel, id=wx.ID_ANY, label="Received data:")

        #combobox for selecting the com-port
        self.comboboxCOMport = wx.ComboBox(self.panel,id=wx.ID_ANY,value="Select port...",choices=self.getComportsList(),size=(130,35))
        self.comboboxCOMport.Bind(wx.EVT_COMBOBOX, self.cmbChanged)

        #input-field for sending bytes in HEX format
        self.inputHexLabel = wx.StaticText(self.panel,id=wx.ID_ANY,label="Send data (HEX):")
        self.inputtextHEX = wx.TextCtrl(self.panel,id=wx.ID_ANY, size=(150,25),style = wx.TE_CHARWRAP)
        self.inputHexCheckbox = wx.CheckBox(self.panel,id=wx.ID_ANY,label="Send hex data only")
        self.inputSendCRCheckBox = wx.CheckBox(self.panel,id=wx.ID_ANY,label="Send Carriage feed/return CR (0x0D)")
        self.inputSendLFCheckBox = wx.CheckBox(self.panel,id=wx.ID_ANY,label="Send Line feed LF (0x0A)")
        self.inputtextHEX.Bind(wx.EVT_KEY_UP,self.hexboxtextChanged)
        self.inputHexCheckbox.Bind(wx.EVT_CHECKBOX,self.sendHexDataChecked)

        self.inputSendLFCheckBox.SetValue(True)
        self.inputSendCRCheckBox.SetValue(True)


        # buttons 
        self.btn_cnct = wx.Button(self.panel, label="Connect")
        self.btn_cnct.Bind(wx.EVT_BUTTON, self.connectToUSBISS)
        self.btn_send = wx.Button(self.panel, label="Send")
        self.btn_send.Bind(wx.EVT_BUTTON, self.sendSerialData)
        

        # alignment and positioning
        wsz = wx.BoxSizer(wx.VERTICAL)          # main vertical sizer
        wsz_hor = wx.BoxSizer(wx.HORIZONTAL)    # first row sizer

        # ----- First row -----
        #Port and speed
        wsz_hor.Add(self.comboboxCOMport,0, flag = wx.RIGHT | wx.LEFT |wx.ALIGN_TOP, border = 10)
        wsz_hor.Add(self._comboboxSpeed,0, wx.RIGHT, border=10)
        #Connect + info
        wsz_hor.Add(self.btn_cnct,0, flag=wx.LEFT | wx.ALIGN_TOP, border = 0)
        wsz_hor.Add(self.infotext,0,wx.LEFT | wx.TOP | wx.ALIGN_CENTER_HORIZONTAL, border = 7)
        wsz.Add(wsz_hor, flag=wx.EXPAND | wx.TOP, border = 10, proportion=1)

        # ----- Second row (receive data) -----
        # Received data window
        wsz.Add(self.inputtextlabel,0, wx.LEFT | wx.ALIGN_LEFT | wx.ALIGN_BOTTOM, border = 10)  # add to vertical
        wsz.Add(self.inputtext,0,wx.LEFT | wx.BOTTOM | wx.ALIGN_TOP,border = 10)                # add to vertical


        # ----- Third Row -----
        # Send user data window
        wsz.Add(self.outputtextlabel,0,wx.LEFT,border = 10)             # add to vertical
        wsz_data_hor = wx.BoxSizer(wx.HORIZONTAL)
        wsz_data_hor.Add(self.outputtext,0,wx.LEFT | wx.BOTTOM | wx.ALIGN_TOP,border = 10)

        # -- Right-side containter for the label, input, checkbox and button
        wsz_data_hor_side = wx.BoxSizer(wx.VERTICAL)
        wsz_data_hor_side.Add(self.inputHexLabel,0,wx.LEFT, border=10)
        wsz_data_hor_side.Add(self.inputtextHEX,0,wx.LEFT,border = 10)
        wsz_data_hor_side.Add(self.inputHexCheckbox,0,wx.LEFT|wx.BOTTOM,border=10)
        wsz_data_hor_side.Add(self.inputSendCRCheckBox,0,wx.LEFT|wx.BOTTOM,border=10)
        wsz_data_hor_side.Add(self.inputSendLFCheckBox,0,wx.LEFT|wx.BOTTOM,border=10)
        wsz_data_hor_side.Add(self.btn_send,0, wx.LEFT | wx.RIGHT | wx.ALIGN_LEFT, border = 10)
        wsz_data_hor.Add(wsz_data_hor_side,flag=wx.ALIGN_TOP,border=0)

        wsz.Add(wsz_data_hor,flag= wx.ALIGN_TOP,border=10, proportion=1) # add to vertical
        
        self.btn_cnct.SetMinSize(size=(80,30))
        self.disableControls()
##        self.outputtext.Disable()
##        self.btn_cnct.Disable()
##        self.btn_send.Disable()
##        self.inputtextHEX.Disable()
##        self.inputHexCheckbox.Disable()
        
        #self.panel.SetSizerAndFit(wsz,True)
        self.panel.SetSizer(wsz)
        self.Show()

        

    def cmbChanged(self,event):
        p = self.comboboxCOMport.GetValue()
        self.btn_cnct.Enable()
        #print(p)

    def sendHexDataChecked(self, event):
        if self.inputHexCheckbox.GetValue() == True:
            self.outputtext.Disable()
            self.inputtextHEX.Enable()
            self.inputSendLFCheckBox.Disable()
            self.inputSendCRCheckBox.Disable()
        else:
            self.outputtext.Enable()
            self.inputtextHEX.Disable()
            self.inputSendLFCheckBox.Enable()
            self.inputSendCRCheckBox.Enable()

    def getComportsList(self):
        coms = list()
        i = 0
        for port in serial.tools.list_ports.comports():
            coms.append(str(port)[0:5])
            #print (coms[i])
            i += 1
        return coms

    def connectToUSBISS(self, event):

        if self.btn_cnct.GetLabel() == "Connect":
            self._iss = UsbIss()
            p = self.comboboxCOMport.GetValue()
            self._iss.open(p)
            try:
                self._id = self._iss.read_module_id()
            except UsbIssError as e:
                wx.MessageBox("Module not identified!","Module not identified!",wx.OK,self)
                self._id = 99
            
            if self._id != 7:
                self.infotext.SetLabel("Error: Module not identified! Port closed.")
                self._iss.close()
                self._iss = None
            else:
                self._fwv = self._iss.read_fw_version()
                self._ser = self._iss.read_serial_number()
                speed = self.getSelectedPortSpeed(self._comboboxSpeed.GetStringSelection())
                self._iss.setup_serial(speed,defs.IOType.DIGITAL_INPUT,defs.IOType.DIGITAL_INPUT)
                self._currmode = self._iss.read_iss_mode()
                txt = _infotext.format(self._id,self._fwv,self._ser,self._currmode)
                self.infotext.SetLabel(txt)
                self.btn_cnct.SetLabel("Disconnect")
                self.enableControls()
                self.panel.Layout()
                #start receiving in separate thread
                self.updateTimer.Start(milliseconds=10,oneShot=wx.TIMER_CONTINUOUS)
                
        else:
            self.updateTimer.Stop()
            self._iss.close()
            self._iss = None
            self.infotext.SetLabel("Connection closed...")
            self.btn_cnct.SetLabel("Connect")
            self.disableControls()
            self.btn_cnct.Enable()

    def disableControls(self):
        self.outputtext.Disable()
        self.btn_cnct.Disable()
        self.btn_send.Disable()
        self.inputtextHEX.Disable()
        self.inputHexCheckbox.Disable()
        self.inputtext.Disable()
        self.inputSendLFCheckBox.Disable()
        self.inputSendCRCheckBox.Disable()

    def enableControls(self):
        self.outputtext.Enable()
        self.btn_send.Enable()
        self.inputHexCheckbox.Enable()
        self.inputtextHEX.Enable()
        
        if self.inputHexCheckbox.GetValue() == True:
            self.inputtextHEX.Enable()
            self.outputtext.Disable()
        else:
            self.outputtext.Enable()
            self.inputSendLFCheckBox.Enable()
            self.inputSendCRCheckBox.Enable()
            self.inputtextHEX.Disable()
        
    def handleSerialData(self):
        mystr = str()
        try:
            # Get bytes from the USB ISS serial port
            r_bytes = self._iss.serial.receive()
            if r_bytes is not None:
                if len(r_bytes) > 0:
                    for b in r_bytes:
                        mystr += chr(b)
                    mystr = mystr.rstrip()
                    #print(mystr)
                return mystr.rstrip()
        except UsbIssError as e:
            print("Error: "+str(e))

    def updateReadDataWindow(self, event):
        if self._iss is None:
            self.updateTimer.Stop()
        data = self.handleSerialData()
        if data is not None:
            self.inputtext.AppendText(data)
            
    def hexboxtextChanged(self, event):
        key = event.GetUnicodeKey()
        if key == 13:
            try:
                inChrs = self.inputtextHEX.GetValue().rstrip().upper()
                hexStr = bytes.fromhex(inChrs)
                hexStrConv = binascii.hexlify(hexStr)
                #print(hexStr)
                #print(hexStrConv)
                self._iss.serial.transmit(list(hexStr))

            except ValueError as e:
                #wrongInputMSg(self,e)
                wx.MessageBox("Please enter ONLY HEX values (without 0x -prefix) with even count. For example: \"aa55ff\".","Wrong number of bytes!",wx.OK,self)
                
                print(str(e))
    def getHexData(self):
        _hexStr = 0
        try:
            _inChrs = self.inputtextHEX.GetValue().rstrip().upper()
            _hexStr = bytes.fromhex(_inChrs)
        except ValueError as e:
            wx.MessageBox("Please enter ONLY HEX values (without 0x -prefix) with even count. For example: \"aa55ff\".","Wrong number of bytes!",wx.OK,self)

        return _hexStr
    def sendSerialData(self,event):
        if self._iss is not None:
            if self.inputHexCheckbox.GetValue() == True:
                data = self.getHexData()
                if data != 0:
                    self._iss.serial.transmit(list(data))
            else:
                data = self.outputtext.GetValue()
                if self.inputSendLFCheckBox.GetValue() == True:
                    if self.inputSendCRCheckBox.GetValue():
                        data = data.replace('\n','\r\n')
                else:
                    data = data.replace('\n','')
                if len(data) > 0:
                    self._iss.serial.transmit(list(bytearray(data,'utf-8')))
            #self._iss.serial.transmit([0x64,0x61,0x74,0x61])
            #time.sleep(0.5)
            #response = self._iss.serial.receive()
        else:
            wx.MessageBox("No Connection...","Cannot send data!",wx.OK,self)

    def getSelectedPortSpeed(self, comp):
        sl = self._comspeeds
        i = 0
        #handle the special case 1M here directly
        if comp == "1M":
            return 1000000
        while i < len(sl):
            if comp == sl[i]:
                return int(sl[i])
            i += 1    
        return 115200 #default value

if __name__ == "__main__":
    #Define the base-app window
    app = wx.App()
    frame = USBISS_Serial_Interface()
    frame.Show()
    app.MainLoop()
