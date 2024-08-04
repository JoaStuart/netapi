import termios
import serial


def read():
    port = "/dev/ttyACM0"
    f = open(port)
    attrs = termios.tcgetattr(f)
    attrs[2] = attrs[2] & termios.HUPCL
    termios.tcsetattr(f, termios.TCSAFLUSH, attrs)
    f.close()
    se = serial.Serial()
    se.baudrate = 9600
    se.port = port
    se.open()

    se.write(b"r")
    se.flush()
    data = se.read_until()
    se.close()
    return data


if __name__ == "__main__":
    print(read())
