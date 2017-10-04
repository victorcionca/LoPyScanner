import sys
import socket
from lopy_serial_if import Pyboard
from time import sleep
import signal

SERVER='157.190.52.166'
PORT=12345

# Open serial connection to LoPy
if len(sys.argv) < 2:
    print('Usage: server.py <tty>')
    sys.exit(1)

lopy_if = Pyboard(sys.argv[1])

# Before we start, upload the receiver code
print('Uploading sender code')
lopy_if.put('/flash/sender.py', 'sender.py')
# Soft reboot to get the receiver code loaded
print('Rebooting')
lopy_if.reboot()
# Import functions
print('Importing functions')
output = lopy_if.exec_('from sender import run_one_round')
print('Sender ready', output)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# LoRa parameters
sf = range(7, 12+1)
bw = [0,1,2]
cr = [0,1,2,3]
pw = range(2, 14+1)

def build_packet(cfg_if, sf, bw_idx, cr_idx, pw):
    """
    Creates a packet that contains the configuration.
    Packet structure is:
    next | CFG_ID (2B) | SF | BW_idx | CR_idx | Power
    """
    pkt = 'next'\
            +chr(cfg_id>>8)+chr(cfg_id&0x00ff)\
            +chr(sf)+chr(bw_idx)+chr(cr_idx)+chr(pw)
    return bytearray(pkt, 'utf-8')

def write_configuration(cfg_id, sf, bw_idx, CR_idx, pw):
    config_str = "config = {{\
                            'cfg_id':{0},\
                            'sf':{1},\
                            'bw_idx':{2},\
                            'cr_idx':{3},\
                            'pw':{4}\
                            }}".format(cfg_id, sf, bw_idx, CR_idx, pw)
    return config_str

from itertools import product
cfg_id = 0
for (_sf, _bw, _cr, _pw) in product(sf, bw, cr, pw):
    # Send configuration to destination
    pkt = build_packet(cfg_id, _sf, _bw, _cr, _pw)
    s.sendto(pkt, (SERVER, PORT))
    # Wait so that destination is ready
    sleep(5)
    # First perform hard reboot to reset LoRa stack
    lopy_if.hard_reboot()
    # Wait a bit
    sleep(1)
    # Import functions
    output = lopy_if.exec_('from sender import run_one_round')
    # Tell sender to start new round
    config_str = write_configuration(cfg_id, _sf, _bw, _cr, _pw)
    print('Running next round: run_one_round(%s)'%config_str)
    lopy_if.exec_no_follow('run_one_round(%s)'%config_str)
    # Wait for sender to finish
    output = lopy_if.follow(timeout=None)
    print(output)
