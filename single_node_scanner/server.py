import sys
import socket
from lopy_serial_if import Pyboard
from time import sleep
import signal
from textwrap import dedent

RESULT_PATH='/flash/result_%05d'
LOCAL_RESULT_PATH='results/result_%05d'

def int_handler(signum, frame):
    lopy_if.cancel_execution()
    sleep(1)
    print('Saving final logs')
    output_id = int(lopy_if.exec_('persist_round()'))
    print('Downloading',RESULT_PATH%output_id,)
    lopy_if.get(RESULT_PATH%output_id, LOCAL_RESULT_PATH%output_id)
    print('Done')
    sleep(1)
    print('Exiting')
    sys.exit(0)

PORT=12345

def write_configuration(cfg_id, sf, bw_idx, CR_idx, pw):
    config_str = "config = {{\
                            'cfg_id':{0},\
                            'sf':{1},\
                            'bw_idx':{2},\
                            'cr_idx':{3},\
                            'pw':{4}\
                            }}".format(cfg_id, sf, bw_idx, CR_idx, pw)
    return dedent(config_str)


# Open serial connection to LoPy
if len(sys.argv) < 2:
    print('Usage: server.py <tty>')
    sys.exit(1)

# Setup interrupt signal handler
signal.signal(signal.SIGINT, int_handler)

first_time = True

lopy_if = Pyboard(sys.argv[1])

# Before we start, upload the receiver code
print('Uploading receiver code')
lopy_if.put('/flash/receiver.py', 'receiver.py')
# Soft reboot to get the receiver code loaded
print('Rebooting')
lopy_if.reboot()
# Import functions
print('Importing functions')
output = lopy_if.exec_('from receiver import persist_round, run_one_round')
print('Receiver ready', output)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', PORT))

print('Done setup, waiting clients')
while True:
    # Packet structure is 
    # 'next' | CFG_ID (2B) | SF | BW_idx | CR_idx | PW
    # In total 10B
    rcvd, addr = s.recvfrom(10)
    if len(rcvd) < 10:
        print('Length is wrong')
        continue
    if str(rcvd[:4], 'utf-8') == 'next':    # Check header
        print('Received config:', rcvd)
        # Generate configuration string
        cfg_id = (rcvd[4]<<8)+rcvd[5]
        config_str = write_configuration(cfg_id, *rcvd[6:])
        print('Generated configuration')
        # Interrupt running code
        lopy_if.cancel_execution()
        print('Canceled current execution')
        if not first_time:
            # Send command to write logs
            output = lopy_if.exec_('persist_round()')
            print('Wrote logs:',output)
            output = int(output)
            # Download logs from device, for previous config
            lopy_if.get(RESULT_PATH%output, LOCAL_RESULT_PATH%output)
            print('Downloaded logs: results/result_%05d'%output)
            # Delete the logs from the device, to save space
            lopy_if.remove(RESULT_PATH%output)
            print('Deleted logs from device')
        # First perform hard reboot to reset LoRa stack
        lopy_if.hard_reboot()
        # Wait a bit
        sleep(1)
        # Import functions
        output = lopy_if.exec_('from receiver import persist_round, run_one_round')
        # Send command to run round
        print('Running next round: run_one_round(%s)'%config_str)
        lopy_if.exec_no_follow('run_one_round(%s)'%config_str)
        first_time = False
    else:
        print('I Recvd crap', rcvd, rcvd[:4], rcvd[:4] == 'next')
        continue
