from network import LoRa
import socket
import ujson
from time import sleep

# Global variable to store the number of packets received from A
a_pdr = 0

CONFIG_PATH = 'result_%05d'
# LoRa parameters
sf = range(7, 12+1)
bw = [(0,LoRa.BW_125KHZ), (1,LoRa.BW_250KHZ), (2,LoRa.BW_500KHZ)]
cr = [(1, LoRa.CODING_4_5), (2, LoRa.CODING_4_6), (3, LoRa.CODING_4_7), (4, LoRa.CODING_4_8)]
pw = range(2, 14+1)

lora = LoRa(mode=LoRa.LORA)

def setup(config):
    """One time setup"""
    # Init and configure LoRa
    lora.init(mode=LoRa.LORA, tx_power=14)

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

def eval_tx_power():
    """
    Receives the sender probes and evaluates their tx power
    """
    sender_probes = {'A':[0,0], 'B':[0,0]}

    # Start sending
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(False)

    while True:
        p = s.recv(32)
        node_id = str(p[:5], 'utf-8')
        if len(p) < 32:
            sleep(0.05)
            continue
        if node_id[:4] == 'node':
            stats = lora.stats()
            sender_probes[node_id[4]][0] += stats.rssi
            sender_probes[node_id[4]][1] += 1
        elif node_id[:4] == 'done':
            break
    if sender_probes['A'][1] > 0:
        sender_probes['A'][0] /= sender_probes['A'][1]
    else:
        sender_probes['A'][0] = 0
    if sender_probes['B'][1] > 0:
        sender_probes['B'][0] /= sender_probes['B'][1]
    else:
        sender_probes['B'][0] = 0

    print(sender_probes['A'][0], sender_probes['B'][0])
    s.close()

def run_one_round():
    """
    Configures the LoRa based on the stored configuration.
    Runs a new round, recording packet statistics.
    """

    # Clear the round
    a_pdr = 0
    b_pdr = 0

    # Sleep a while to ensure that configuration is set
    sleep(2)

    # Open the lora socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(False)

    # Try to flush any 'done' messages in the Q
    while True:
        try:
            p=s.recv(32)
        except OSError:
            break
        if len(p) < 32:
            break

    # First thing is to broadcast the synch message
    s.send('synch')

    # Start listening for the probes
    while True:
        p = s.recv(32)
        node_id = str(p[:5], 'utf-8')
        if len(p) < 32:
            sleep(0.05)
            continue
        if node_id[:4] == 'node':
            #print('Valid packet')
            stats = lora.stats()
            if node_id[4] == 'A':
                a_pdr += 1
            if node_id[4] == 'B':
                b_pdr += 1
        elif node_id[:4] == 'done':
            #print('Done packet')
            break
        else:
            continue

    s.close()
    print(a_pdr, b_pdr)
