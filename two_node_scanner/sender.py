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

lora = LoRa()
node_id = []

def setup(config, _node_id):
    """Initial setup. Once per round."""
    # To start, disable Wlan and FTP server, seems to cause problems
    import network
    network.Server().deinit()
    network.WLAN().deinit()

    # Init and configure LoRa
    lora.init(mode=LoRa.LORA, tx_power=config['pw'])

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

    node_id.append(_node_id)

def eval_tx_power():
    """
    Sends 10 packets, with the given configuration,
    so that the receiver can estimate the RX power.
    """
    # Start sending
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(True)

    for i in range(10):
        pkt = 'node'+node_id[0]+'1'*27  # header + counter + padding up to 32B
        s.send(pkt)
        rgbled({0:0x7f0000, 1:0x0}[i%2])
        sleep(1)                  # Wait 1s between packets

    s.close()

def run_one_round(offset, blocking):
    """
    Configures the LoRa based on the stored configuration.
    Runs a new round, recording packet statistics.
    Params:
    offset  -- offset of sending packets, from start signal
    """

    # Open comms socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(False)

    # Wait for broadcast message from receiver, as signal to start round
    while True:
        p = s.recv(5)
        if len(p) < 5:
            sleep(0.05)
            continue
        if str(p, 'utf-8') != 'synch':
            sleep(0.05)
            continue
        else:
            break

    s.setblocking(blocking)
    # Signal received, start sending
    pkts_sent = 0
    for i in range(100):
        if offset > 0:
            sleep(offset)               # Create an offset
        pkt = 'node'+node_id[0]+'1'*27  # header + counter + padding up to 32B
        s.send(pkt)
        rgbled({0:0x7f0000, 1:0x0}[i%2])
        if blocking:
	    sleep(0.5)                  # Wait 0.5s between packets
        else:
            sleep(2)                  # Wait 0.5s between packets
        pkts_sent += 1

    print('Round complete '+str(pkts_sent))

    s.close()

def complete_round(config):
    # Reconfigure with higher TX power to make sure that transmission go through
    #lora.init(mode=LoRa.LORA, tx_power=14)

    # Configure LoRa
    #lora.frequency(864000000)
    #lora.sf(config['sf'])
    #lora.bandwidth(bw[config['bw_idx']][1])
    #lora.coding_rate(cr[config['cr_idx']][1])

    # Open comms socket
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(True)

    # Send 5 completion packets to the server to allow it to finish gracefully
    for i in range(5):
        s.send('done'+'1'*28)
        rgbled({0:0x007f00, 1:0x0}[i%2])
        sleep(1)
    s.close()

    # Reset configuration
    #lora.init(mode=LoRa.LORA, tx_power=config['pw'])
