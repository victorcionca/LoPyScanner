from network import LoRa
import socket
import ujson
from time import sleep
from pycom import rgbled, heartbeat

heartbeat(False)

# Parameters
sf = range(7, 12+1)
bw = [(0,LoRa.BW_125KHZ), (1,LoRa.BW_250KHZ), (2,LoRa.BW_500KHZ)]
cr = [(0, LoRa.CODING_4_5), (1, LoRa.CODING_4_6), (2, LoRa.CODING_4_7), (3, LoRa.CODING_4_8)]
pw = range(2, 14+1)


def eval_tx_power(config, node_id):
    """
    Sends 10 packets, with the given configuration,
    so that the receiver can estimate the RX power.
    """
    # Init and configure LoRa
    lora = LoRa(mode=LoRa.LORA, tx_power=config['pw'])

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

    # Start sending
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

    for i in range(10):
        pkt = 'node'+node_id+'1'*27  # header + counter + padding up to 32B
        s.send(pkt)
        rgbled({0:0x7f0000, 1:0x0}[i%2])
        sleep(1)                  # Wait 1s between packets

    s.close()

def run_one_round(config, node_id, offset):
    """
    Configures the LoRa based on the stored configuration.
    Runs a new round, recording packet statistics.
    Params:
    config  -- {'cfg_id', 'sf', 'bw_idx', 'cr_idx', 'pw'}
    node_id -- id to send in packet
    offset  -- offset of sending packets, from start signal
    """

    # Init and configure LoRa
    lora = LoRa(mode=LoRa.LORA, tx_power=config['pw'])

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

    # Open comms socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)

    # Wait for broadcast message from receiver, as signal to start round
    # TODO

    # Signal received, start sending
    pkts_sent = 0
    for i in range(100):
        sleep(offset)               # Create an offset
        pkt = 'node'+node_id+'1'*27  # header + counter + padding up to 32B
        s.send(pkt)
        rgbled({0:0x7f0000, 1:0x0}[i%2])
        sleep(0.5)                  # Wait 0.5s between packets
        pkts_sent += 1

    print('Round complete '+str(pkts_sent))

    s.close()
