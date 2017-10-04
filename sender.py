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


def run_one_round(config):
    """
    Configures the LoRa based on the stored configuration.
    Runs a new round, recording packet statistics.
    Params:
    config  -- {'cfg_id', 'sf', 'bw_idx', 'cr_idx', 'pw'}
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

    for i in range(255):
        pkt = 'pack'+chr(i)+'1'*27  # header + counter + padding up to 32B
        s.send(pkt)
        rgbled({0:0x7f0000, 1:0x0}[i%2])
        sleep(0.5)                  # Wait 0.5s between packets

    print('Round complete')
