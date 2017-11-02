import sys
import signal
import threading
from client_thread import SenderManager


SERVER='157.190.52.166'
PORT=12345

# Open serial connection to LoPy
if len(sys.argv) < 2:
    print('Usage: server.py <tty>')
    sys.exit(1)


s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# LoRa parameters
sf = range(7, 12+1)
bw = [0,1,2]
cr = [0,1,2,3]
pw = range(2, 14+1)

# Packet types
pkt_types = ['init', 'start', 'end']

def init_packet(sf, bw_idx, cr_idx, a_pw, b_pw):
    """
    Creates a packet that contains the configuration.
    Packet structure is (4+5B):
    init | SF | BW_idx | CR_idx | A_power | B_power
    """
    pkt = 'init'\
            +chr(sf)+chr(bw_idx)+chr(cr_idx)\
            +chr(a_pw)+chr(b_pw)
    return bytearray(pkt, 'utf-8')

def stats_packet(a_sent, b_sent):
    pkt = 'fini' + chr(a_sent) + chr(b_sent)
    return bytearray(pkt, 'utf-8')

def write_configuration(sf, bw_idx, CR_idx, pw):
    config_str = "config = {{\
                            'sf':{1},\
                            'bw_idx':{2},\
                            'cr_idx':{3},\
                            'pw':{4}\
                            }}".format(sf, bw_idx, CR_idx, pw)
    return config_str

# We first vary the power
# Node B goes through all the levels
# Node A Tx power is P(B) + P_thresh
# Threshold increases from 0dB until we see > 99% PDR for A
thresh = 0

_sf = 12
_bw = 1
_cr = 0

from itertools import product
lopyA = SenderManager('/dev/ttyUSB0', 'A', first_run=True)
lopyB = SenderManager('/dev/ttyUSB1', 'B', first_run=True)
for b_power in range(2,14):
    # One round has several steps

    prev_pdr = 0
    for a_power in range(b_power, 14+1):
        # Load and initialise LoPy managers
        lopyA = SenderManager('/dev/ttyUSB0', 'A')
        lopyB = SenderManager('/dev/ttyUSB1', 'B')
        config_str = write_configuration(_sf, _bw, _cr, a_power)
        lopyA.connect(config_str)
        config_str = write_configuration(_sf, _bw, _cr, b_power)
        lopyB.connect(config_str)

        # 1. Send configuration to server
        s.sendto(init_packet(_sf, _bw, _cr, a_power, b_power), (SERVER, PORT))
        sleep(1)    # Wait for server to be ready
        # 2. Start evaluating TX power
        lopyA.eval_tx_power()
        lopyB.eval_tx_power()
        # 3. Start experiment
        lopyA.start()
        lopyB.start()
        # Tell server to start the experiment
        s.sendto(bytearray('strt', 'utf-8'), (SERVER, PORT))
        # Wait until experiment is complete
        lopyA.join()
        lopyB.join()
        sent_pkts = (lopyA.txd_packets, lopyB.txd_packets)
        # 4. Send stats to server, notifying it of experiment completion
        s.sendto(stats_packet(*sent_pkts), (SERVER, PORT))
        # 5. Receive results from server, check PDR
        a_pdr = None
        while True:
            # Packet format: 'rslt'|A_PDR (1B)|A_power (1B)|B_power (1B)
            rcvd, addr = s.recvfrom(7)
            if len(rcvd) < 7: continue
            if str(rcvd[:4], 'utf-8') != 'rslt': continue
            a_pdr = rcvd[4]
            actual_a_power = rcvd[5]
            actual_b_power = rcvd[6]
        print(actual_a_power, actual_b_power, send_pkts, a_pdr)
        if a_pdr >= 95 and prev_pdr >= 95:
            # We have reached a satisfactory PDR for A, move to the next B power
            # TODO Persist results here?
            break
        # Otherwise continue increasing the A power
        prev_pdr = a_pdr

