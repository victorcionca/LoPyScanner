from network import LoRa
import socket
import ujson
from time import sleep

round_results = {'config':None, 'results':[]}

CONFIG_PATH = 'result_%05d'
# LoRa parameters
sf = range(7, 12+1)
bw = [(0,LoRa.BW_125KHZ), (1,LoRa.BW_250KHZ), (2,LoRa.BW_500KHZ)]
cr = [(1, LoRa.CODING_4_5), (2, LoRa.CODING_4_6), (3, LoRa.CODING_4_7), (4, LoRa.CODING_4_8)]
pw = range(2, 14+1)

def persist_round():
    """
    Writes the contents of the round status to flash.
    Uses the configuration file to determine the config

    Returns the configuration id of the persisted results
    """
    config = round_results['config']
    with open(CONFIG_PATH%config['cfg_id'], 'w') as f:
        f.write('config:%s\n'%ujson.dumps(round_results['config']))
        for st in round_results['results']:
            f.write('%s\n'%str(st))
    print(config['cfg_id'])

def eval_tx_power(config):
    """
    Receives the sender probes and evaluates their tx power
    """
    sender_probes = {'A':0, 'B':0}

    # Init and configure LoRa
    lora = LoRa(mode=LoRa.LORA, tx_power=config['pw'])

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

    # Start sending
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(False)

    collected = 0
    while collected < 20:
        p = s.recv(32)
        if len(p) < 32 or str(p[:4], 'utf-8') != 'node':
            sleep(0.05)
            continue
        else:
            stats = lora.stats()
            sender_probes[p[5]] += stats.rssi
            collected += 1
    sender_probes['A'] /= 10.0
    sender_probes['B'] /= 10.0

    print(sender_probes['A'], sender_probes['B'])


def run_one_round(config):
    """
    Configures the LoRa based on the stored configuration.
    Runs a new round, recording packet statistics.
    Parameters:
    config  -- configuration dictionary:
               {'sf', 'bw_idx', 'cr_idx', 'pw', 'cfg_id'}
    """

    # Clear the round
    round_results['config'] = config
    round_results['results'] = []

    # Init and configure LoRa
    lora = LoRa(mode=LoRa.LORA, tx_power=config['pw'])

    # Configure LoRa
    lora.frequency(864000000)
    lora.sf(config['sf'])
    lora.bandwidth(bw[config['bw_idx']][1])
    lora.coding_rate(cr[config['cr_idx']][1])

    # Sleep a while to ensure that configuration is set
    sleep(5)


    # Start listening
    s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
    s.setblocking(False)

    while True:
        p = s.recv(32)
        if len(p) < 32 or str(p[:4], 'utf-8') != 'pack':
            sleep(0.05)
            continue
        else:
            stats = lora.stats()
            round_results['results'].append(stats)
