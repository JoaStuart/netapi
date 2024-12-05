from ctypes import (
    wintypes,
    Structure,
    c_wchar,
    c_bool,
    c_ulong,
    c_char,
    c_byte,
    c_uint,
    CFUNCTYPE,
    POINTER,
    byref,
    pointer,
)
from threading import Thread
import traceback

from device.api import APIFunct, APIResult

from ctypes import windll  # type: ignore    Linux does not know the `windll`

user32 = windll.user32  # type: ignore       import because it only exists on
kernel32 = windll.kernel32  # type: ignore   Windows. User is supposed to only
dxva2 = windll.dxva2  # type: ignore         add this FFunc on Windows machines!


class PHYSICAL_MONITOR(Structure):
    _fields_ = (
        ("hPhysicalMonitor", wintypes.HANDLE),
        (
            "szPhysicalMonitorDescription",
            c_wchar * 128,
        ),
    )


class DDC_CI(APIFunct):
    """Implements the DCC/CI protocol using win32 api calls

    Using the APIFunct:
    - 0/1 argument: monitor number and VCP capabilities
    - 2 arguments: check monitor `args[0]` for VCP `args[1]`
    - 3 arguments: set value `args[2]` on monitor `args[0]` for VCP `args[1]`
    """

    MC_MOMENTARY = 0
    MC_SET_PARAMETER = 1

    _MONITOR_ENUM_PROC = CFUNCTYPE(
        c_bool,
        wintypes.HMONITOR,
        wintypes.HDC,
        POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )

    def __init__(self, request, args, body, poll_threaded: bool = False) -> None:
        super().__init__(request, args, body)

        self.PHY_MONITORS = {}
        self._poll_monitors(poll_threaded)

    def api(self) -> APIResult:
        ret = {}
        try:
            if len(self.args) < 2:
                return APIResult.by_json(self.PHY_MONITORS)
            elif len(self.args) == 2:
                mon_arg = self.args[0]
                monitor = []
                if mon_arg == "*":
                    for k, v in self.PHY_MONITORS.items():
                        if v is not None:
                            monitor.append(k)
                else:
                    monitor.append(int(mon_arg))

                for m in monitor:
                    if self.PHY_MONITORS.get(m, None) == None:
                        ret |= {m: "Monitor not found or no capabilities reported"}

                    vcp = int(self.args[1], base=0)

                    try:
                        ret |= {m: self.current_value(m, vcp)}
                    except ValueError:
                        ret |= {m: f"Error getting VCP {vcp:02X} on monitor {monitor}"}

            elif len(self.args) == 3:
                mon_arg = self.args[0]
                monitor = []
                if mon_arg == "*":
                    for k, v in self.PHY_MONITORS.items():
                        if v is not None:
                            monitor.append(k)
                else:
                    monitor.append(int(mon_arg))

                for m in monitor:
                    if self.PHY_MONITORS.get(m, None) == None:
                        ret |= {m: "Monitor not found or no capabilities reported"}

                    vcp = int(self.args[1], base=0)
                    value = int(self.args[2], base=0)

                    try:
                        self.set_value(m, vcp, value)
                    except ValueError:
                        ret |= {m: f"Error setting VCP {vcp:02X} on monitor {monitor}"}

        except Exception:
            ret |= {
                "msg": "Arguments must be integers",
                "tback": traceback.format_exc(),
            }

        for k, v in self.PHY_MONITORS.items():
            dxva2.DestroyPhysicalMonitor(k)

        return APIResult.by_json(ret)

    def _poll_monitors(self, threaded: bool):
        hmon_list = self.__poll_hmonitors()
        self.__poll_physical_monitors(hmon_list)

        if threaded:
            Thread(target=self._poll_capabilities, daemon=True).start()
        else:
            self._poll_capabilities()

    def __poll_hmonitors(self) -> list[int]:
        hmon_list = []

        def monitor_enum_proc(hmonitor, hdc, lprc, dw_data):
            hmon_list.append(hmonitor)
            return True

        callback = self._MONITOR_ENUM_PROC(monitor_enum_proc)
        user32.EnumDisplayMonitors(None, None, callback, None)

        return hmon_list

    def __poll_physical_monitors(self, hmon_list: list[int]) -> None:
        for hmon in hmon_list:
            num = c_ulong()
            dxva2.GetNumberOfPhysicalMonitorsFromHMONITOR(hmon, pointer(num)),

            phy_mon = (PHYSICAL_MONITOR * num.value)()
            self._check(
                dxva2.GetPhysicalMonitorsFromHMONITOR(
                    hmon, num.value, pointer(phy_mon)
                ),
                1,
            )

            for i in phy_mon:
                self.PHY_MONITORS[i.hPhysicalMonitor] = None

    def _poll_capabilities(self) -> None:
        for i in self.PHY_MONITORS:
            strlen = c_ulong()
            dxva2.GetCapabilitiesStringLength(i, pointer(strlen))

            if strlen.value == 0:
                continue

            strarr = (c_char * strlen.value)()
            dxva2.CapabilitiesRequestAndCapabilitiesReply(
                i, pointer(strarr), strlen.value
            )

            self.PHY_MONITORS[i] = strarr.raw.decode(errors="replace")

    def capable_monitors(self) -> list[int]:
        capable = []
        for k, v in self.PHY_MONITORS.items():
            if v is not None:
                capable.append(k)
        return capable

    def _check(self, returned_val: int, expected_val: int) -> None:
        if returned_val != expected_val:
            err = returned_val if returned_val > 1 else kernel32.GetLastError()
            print(f"Error: {hex(err & 0xFFFFFFFF)[2:].upper()}")

    def current_value(self, monitor: int, vcp: int) -> dict[str, int]:
        if self.PHY_MONITORS.get(monitor, None) == None:
            raise ValueError(f"Monitor {monitor} not found or no capabilities reported")

        pvct = c_uint()
        pdwCurrentValue = c_ulong()
        pdwMaximumValue = c_ulong()

        self._check(
            dxva2.GetVCPFeatureAndVCPFeatureReply(
                monitor,
                c_byte(vcp),
                byref(pvct),
                byref(pdwCurrentValue),
                byref(pdwMaximumValue),
            ),
            1,
        )

        return {
            "pvct": pvct.value,
            "pdwCurrentValue": pdwCurrentValue.value,
            "pdwMaximumValue": pdwMaximumValue.value,
        }

    def set_value(self, monitor: int, vcp: int, value: int) -> None:
        if self.PHY_MONITORS.get(monitor, None) == None:
            raise ValueError(f"Monitor {monitor} not found or no capabilities reported")

        self._check(
            dxva2.SetVCPFeature(monitor, c_byte(vcp), c_ulong(value)),
            1,
        )

    def send_command(self, monitor: int, command: int) -> None:
        result = dxva2.SetVCPFeature(monitor, command, 1)
        if result == 0:
            print(f"Failed to send command {command:02X}. Error code: {result}")


if __name__ == "__main__":
    ddcci = DDC_CI(None, None, None, False)

    while True:
        print(f"\r{ddcci.capable_monitors()}")
        try:
            monitor = int(input("Monitor: "), base=0)
        except KeyboardInterrupt:
            break
        while True:
            try:
                code = input("Code [s/c/q][xx]: ")

                if code.startswith("s"):
                    if "." not in code[1:]:
                        print("No value provided")
                        continue

                    ddcci.set_value(
                        monitor,
                        int(code[1:].split(".", 1)[0], base=16),
                        int(code[1:].split(".", 1)[1]),
                    )
                elif code.startswith("c"):
                    ddcci.send_command(monitor, int(code[1:], base=16))
                elif code.startswith("q"):
                    print(ddcci.current_value(monitor, int(code[1:], base=16)))
                else:
                    print(ddcci.PHY_MONITORS.get(monitor, None))
            except KeyboardInterrupt:
                break
