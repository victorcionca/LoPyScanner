import sys
import time
from textwrap import dedent

class PyboardError(BaseException):
    pass

BUFFER_SIZE = 32
class Pyboard:
    def __init__(self, device, baudrate=115200, wait=0):
        import serial
        delayed = False
        for attempt in range(wait + 1):
            try:
                self.serial = serial.Serial(device, baudrate=baudrate, interCharTimeout=1)
                break
            except (OSError, IOError): # Py2 and Py3 have different errors
                if wait == 0:
                    continue
                if attempt == 0:
                    sys.stdout.write('Waiting {} seconds for pyboard '.format(wait))
                    delayed = True
            time.sleep(1)
            sys.stdout.write('.')
            sys.stdout.flush()
        else:
            if delayed:
                print('')
            raise PyboardError('failed to access ' + device)
        if delayed:
            print('')

    def close(self):
        self.serial.close()

    def read_until(self, min_num_bytes, ending, timeout=10, data_consumer=None):
        data = self.serial.read(min_num_bytes)
        if data_consumer:
            data_consumer(data)
        timeout_count = 0
        while True:
            if data.endswith(ending):
                break
            elif self.serial.inWaiting() > 0:
                new_data = self.serial.read(1)
                data = data + new_data
                if data_consumer:
                    data_consumer(new_data)
                timeout_count = 0
            else:
                timeout_count += 1
                if timeout is not None and timeout_count >= 100 * timeout:
                    break
                time.sleep(0.01)
        return data

    def cancel_execution(self):
        """
        Cancels any current execution by sending ctrl-C
        """
        self.serial.write(b'\r\x03\x03') # ctrl-C twice: interrupt any running program

        # flush input (without relying on serial.flushInput())
        n = self.serial.inWaiting()
        while n > 0:
            self.serial.read(n)
            n = self.serial.inWaiting()

    def follow(self, timeout, data_consumer=None):
        # wait for normal output
        data = self.read_until(1, b'\x04', timeout=timeout, data_consumer=data_consumer)
        if not data.endswith(b'\x04'):
            raise PyboardError('timeout waiting for first EOF reception')
        data = data[:-1]

        # wait for error output
        data_err = self.read_until(1, b'\x04', timeout=timeout)
        if not data_err.endswith(b'\x04'):
            raise PyboardError('timeout waiting for second EOF reception')
        data_err = data_err[:-1]

        # return normal and error output
        return data, data_err

    def exec_raw_no_follow(self, command):
        if isinstance(command, bytes):
            command_bytes = command
        else:
            command_bytes = bytes(command, encoding='utf8')

        # check we have a prompt
        #data = self.read_until(1, b'>')
        #if not data.endswith(b'>'):
        #    raise PyboardError('could not enter raw repl')

        # write command
        for i in range(0, len(command_bytes), 256):
            self.serial.write(command_bytes[i:min(i + 256, len(command_bytes))])
            time.sleep(0.01)
        self.serial.write(b'\x04')

        # check if we could exec command
        data = self.serial.read(2)
        if data != b'OK':
            raise PyboardError('could not exec command')

    def exec_raw(self, command, timeout=10, data_consumer=None):
        self.enter_raw_repl()
        self.exec_raw_no_follow(command);
        ret = self.follow(timeout, data_consumer)
        self.exit_raw_repl()
        return ret

    def exec_no_follow(self, command):
        self.enter_raw_repl()
        self.exec_raw_no_follow(command);
        self.exit_raw_repl()

    def exec_(self, command, timeout=10):
        ret, ret_err = self.exec_raw(command, timeout)
        if ret_err:
            raise PyboardError('exception', ret, ret_err)
        return ret

    def reboot(self):
        """ Soft Reboots the system"""
        self.serial.write(b'\r\x03\x03') # ctrl-C twice: interrupt any running program
        self.serial.write(b'\x04') # ctrl-D: soft reset
        data = self.read_until(1, b'soft reboot\r\n')
        if not data.endswith(b'soft reboot\r\n'):
            print(data)
            raise PyboardError('could not enter raw repl')
        time.sleep(1)
        self.flush_input()

    def hard_reboot(self):
        """Performs hard reboot (machine)"""
        self.exec_('import machine')
        self.exec_no_follow('machine.reset()')
        time.sleep(1)
        self.flush_input()

    def flush_input(self):
        # flush input (without relying on serial.flushInput())
        n = self.serial.inWaiting()
        while n > 0:
            self.serial.read(n)
            n = self.serial.inWaiting()

    def enter_raw_repl(self):
        """
        Cancel any ongoing execution and force the board into raw mode.
        Originally from ampy/pyboard.py
        Removed the part that was rebooting the board.
        """
        self.serial.write(b'\r\x03\x03') # ctrl-C twice: interrupt any running program

        self.flush_input()

        self.serial.write(b'\r\x01') # ctrl-A: enter raw REPL
        data = self.read_until(1, b'raw REPL; CTRL-B to exit\r\n>')
        if not data.endswith(b'raw REPL; CTRL-B to exit\r\n>'):
            print(data)
            raise PyboardError('could not enter raw repl')

    def exit_raw_repl(self):
        self.serial.write(b'\r\x02') # ctrl-B: enter friendly REPL

    def put(self, py_filename, local_filename):
        """Create or update the specified file with the provided data.
        Originally from ampy/files.py
        """
        # Open the file locally
        data = None
        with open(local_filename) as f:
            data = ''.join(f.readlines())
        # Open the file for writing on the board and write chunks of data.
        self.enter_raw_repl()
        self.exec_("f = open('{0}', 'wb')".format(py_filename))
        size = len(data)
        # Loop through and write a buffer size chunk of data at a time.
        for i in range(0, size, BUFFER_SIZE):
            chunk_size = min(BUFFER_SIZE, size-i)
            chunk = repr(data[i:i+chunk_size])
            # Make sure to send explicit byte strings (handles python 2 compatibility).
            if not chunk.startswith('b'):
                chunk = 'b' + chunk
            self.exec_("f.write({0})".format(chunk))
        self.exec_('f.close()')
        self.exit_raw_repl()

    def get(self, py_filename, local_filename):
        """Retrieve the contents of the specified file and return its contents
        as a byte string.
        """
        # Open the file and read it a few bytes at a time and print out the
        # raw bytes.  Be careful not to overload the UART buffer so only write
        # a few bytes at a time, and don't use print since it adds newlines and
        # expects string data.
        command = """
            import sys
            with open('{0}', 'rb') as infile:
                while True:
                    result = infile.read({1})
                    if result == b'':
                        break
                    len = sys.stdout.write(result)
        """.format(py_filename, BUFFER_SIZE)
        self.enter_raw_repl()
        try:
            out = self.exec_(dedent(command))
        except PyboardError as ex:
            # Check if this is an OSError #2, i.e. file doesn't exist and
            # rethrow it as something more descriptive.
            if ex.args[2].decode('utf-8').find('OSError: [Errno 2] ENOENT') != -1:
                raise RuntimeError('No such file: {0}'.format(local_filename))
            else:
                raise ex
        self.exit_raw_repl()
        with open(local_filename, 'wb') as f:
            f.write(out)

    def remove(self, py_filename):
        """Remove the specified file from the pyboard
        """
        command = """
            import uos
            uos.remove('{0}')
        """.format(py_filename)
        try:
            out = self.exec_(dedent(command))
        except PyboardError as ex:
            # Check if this is an OSError #2, i.e. file doesn't exist and
            # rethrow it as something more descriptive.
            if ex.args[2].decode('utf-8').find('OSError: [Errno 2] ENOENT') != -1:
                raise RuntimeError('No such file: {0}'.format(py_filename))
            else:
                raise ex
