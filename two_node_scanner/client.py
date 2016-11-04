import sys
import signal
import threading
import socket
from time import sleep
from client_thread import SenderManager


SERVER='157.190.52.166'
PORT=12345

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# LoRa parameters
sf = range(7, 12+1)
bw = [0,1,2]
cr = [0,1,2,3]
pw = range(2, 14+1)

# Packet types
pkt_types = ['init', 'strt', 'end']

# Results file
results_file = 'results.csv'

def config_packet(pkt_type, sf, bw_idx, cr_idx, a_pw, b_pw):
    """
    Creates a packet that contains the configuration.
    Packet structure is (4+5B):
    init | SF | BW_idx | CR_idx | A_power | B_power
    """
    pkt = pkt_type\
            +chr(sf)+chr(bw_idx)+chr(cr_idx)\
            +chr(a_pw)+chr(b_pw)
    return bytearray(pkt, 'utf-8')

def stats_packet(a_sent, b_sent):
    pkt = 'fini' + chr(a_sent) + chr(b_sent)
    return bytearray(pkt, 'utf-8')

def write_configuration(sf, bw_idx, CR_idx, pw):
    config_str = "{{'sf':{0}, 'bw_idx':{1}, 'cr_idx':{2}, 'pw':{3} }}"\
			.format(sf, bw_idx, CR_idx, pw)
    return config_str

def persist_results(path, a_pwr, b_pwr, act_a_pwr, act_b_pwr, a_pdr, b_pdr):
    """
    Adds results to the results file in path.
    If the file does not exist, it will be created
    """
    with open(path, 'a') as f:
        f.write('%d,%d,%d,%d,%d,%d\n'%(a_pwr,b_pwr,act_a_pwr,act_b_pwr,a_pdr,b_pdr))

# We first vary the power
# Node B goes through all the levels
# Node A Tx power is P(B) + P_thresh
# Threshold increases from 0dB until we see > 99% PDR for A
thresh = 0

_sf = 12
_bw = 1
_cr = 0

from itertools import product
SenderManager.upload_code('/dev/ttyUSB0')
SenderManager.upload_code('/dev/ttyUSB1')
for b_power in range(2,14):
    # One round has several steps

    prev_pdr = 0
    for a_power in range(b_power, 14+1):
        print('Testing with A=%d, B=%d'%(a_power, b_power))
        # Load and initialise LoPy managers
        lopyA = SenderManager('/dev/ttyUSB1', 'A', leader=True)
        lopyB = SenderManager('/dev/ttyUSB0', 'B')
        config_str = write_configuration(_sf, _bw, _cr, a_power)
        lopyA.setup(config_str)
        config_str = write_configuration(_sf, _bw, _cr, b_power)
        lopyB.setup(config_str)

        # 1. Send configuration to server
        print('Sending configuration to server')
        s.sendto(config_packet('init', _sf, _bw, _cr, a_power, b_power), (SERVER, PORT))
        sleep(3)    # Wait for server to be ready
        # 2. Start evaluating TX power.
        #    Both block but that is the intended functionality,
        #    they need to run in sequence.
        lopyA.eval_tx_power(False)
        lopyB.eval_tx_power(True)
        print('Done evaluating power, starting exp')
        # 3. Start experiment. Non-blocking
        lopyA.start()
        lopyB.start()
        # Tell server to start the experiment
        s.sendto(config_packet('strt', _sf, _bw, _cr, a_power, b_power), (SERVER, PORT))
        # Wait until experiment is complete
        lopyA.join()
        lopyB.join()
        sent_pkts = (lopyA.txd_packets, lopyB.txd_packets)
        print('A sent %d; B sent %d'%sent_pkts)
        # 4. Send stats to server, notifying it of experiment completion
        s.sendto(stats_packet(*sent_pkts), (SERVER, PORT))
        # 5. Receive results from server, check PDR
        a_pdr = None
        b_pdr = None
        print('Waiting for results from server...',)
        while True:
            # Packet format: 'rslt'|A_PDR (1B)|B_PDR (1B)A_power (1B)|B_power (1B)
            rcvd, addr = s.recvfrom(8)
            print(rcvd, len(rcvd))
            if len(rcvd) < 8:
                print('Length wrong')
                continue
            if str(rcvd[:4], 'utf-8') != 'rslt':
                print('Prefix wrong')
                continue
            a_pdr = rcvd[4]
            b_pdr = rcvd[5]
            actual_a_power = -rcvd[6]
            actual_b_power = -rcvd[7]
            break
        print(actual_a_power, actual_b_power, sent_pkts, a_pdr, b_pdr)
        persist_results(results_file, a_power, b_power, actual_a_power, actual_b_power, a_pdr, b_pdr)
        if a_pdr >= 95 and prev_pdr >= 95:
            # We have reached a satisfactory PDR for A, move to the next B power
            print('Found satisfactory threshold, increasing B\'s power now')
            break
        # Otherwise continue increasing the A power
        prev_pdr = a_pdr

