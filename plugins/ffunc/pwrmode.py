import ctypes
import os
from device.api import APIFunct
import locations


class InsydeDCHU:
    def __init__(self) -> None:
        self._dchuDLL = ctypes.cdll.LoadLibrary(
            os.path.join(locations.ROOT, "resources", "dll", "InsydeDCHU.dll")
        )

    def get_bytes_uint(self, val):
        a = bytes(ctypes.c_uint32(val))
        arra = (ctypes.c_byte * len(a))()
        for i in range(len(a)):
            arra[i] = ctypes.c_byte(a[i])

        return arra

    def get_power_mode(self) -> int:
        out = ctypes.c_byte(0)
        self._dchuDLL.ReadAppSettings(1, 1, 1, ctypes.byref(out))
        return out.value

    def set_power_mode(self, pwr_mode: int) -> None:
        self.set_wmi(121, 25, pwr_mode)
        inp = ctypes.c_byte(pwr_mode)
        self._dchuDLL.WriteAppSettings(1, 1, 1, ctypes.byref(inp))

    def set_wmi(self, command, subcommand, data):
        array = self.get_bytes_uint(data)
        array[3] = ctypes.c_byte(subcommand)

        return self._dchuDLL.SetDCHU_Data(command, ctypes.byref(array), len(array))


class PwrMode(APIFunct):
    """JoaLaptop specific BIOS API call to change PowerMode"""

    def api(self) -> dict | tuple[bytes, str]:
        dchu = InsydeDCHU()

        if len(self.args) == 0:
            return {"pwrmode": dchu.get_power_mode()}

        try:
            pwrmode = int(self.args[0])
            if pwrmode < 0 or pwrmode > 3:
                raise ValueError()

            dchu.set_power_mode(pwrmode)
            return {}
        except ValueError:
            return {"pwrmode": "Not a valid PowerMode!"}
