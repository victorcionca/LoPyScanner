import sys
# Hack to allow loading of the lopy_serial_if module from the parent directory
import os
parent = os.path.join(os.path.dirname(__file__), '..')
sys.path.append(parent)
import socket
from lopy_serial_if import Pyboard
from time import sleep

RESULT_PATH='/flash/result_%05d'
LOCAL_RESULT_PATH='results/result_%05d'


PORT=12345

def write_configuration(sf, bw_idx, CR_idx):
    config_str = "config = {{'sf':{0}, 'bw_idx':{1}, 'cr_idx':{2}}}"\
                            .format(sf, bw_idx, CR_idx)
    return config_str


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
output = lopy_if.exec_('import receiver')
print('Receiver ready', output)

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(('', PORT))

round_stats = {'a_pwr':0, 'b_pwr':0, 'a_pdr':0}

def init_lopy(lopy_if, config):
    print('Rebooting')
    lopy_if.hard_reboot()
    sleep(1)
    # Import functions
    print('Importing functions')
    output = lopy_if.exec_('import receiver')
    lopy_if.exec_('receiver.setup(%s)'%config)
    print('Receiver ready', output)

def prepare_power_eval(sock, addr):
    """
    First step, receive probe packets from the senders and
    measure their RX power.
    """
    cfg_bytes, = sock.recvfrom(5)
    [sf,bw_idx,cr_idx,a_pw,b_pw] = cfg_bytes
    cfg_str = write_configuration(sf,bw_idx,cr_idx)
    print('Starting power eval with config %s', cfg_str)
    # Prepare receiver for a new round. Blocking, <2s
    init_lopy(lopy_if, cfg_str)
    # Put receiver node into eval tx mode
    lopy_if.exec_no_follow('receiver.eval_tx_power()')
    # Read average values from receiver. Blocking, takes 20s
    output = lopy_if.follow(timeout=None)
    # Store these values in global variables
    round_stats['a_pwr'] = int(output.split())[0]
    round_stats['b_pwr'] = int(output.split())[1]
    print(round_stats)

def start_experiment(sock, addr):
    cfg_bytes, = sock.recvfrom(5)
    [sf,bw_idx,cr_idx,a_pw,b_pw] = cfg_bytes
    cfg_str = write_configuration(sf,bw_idx,cr_idx)
    # Tell RX to signal start exp to the two senders.
    print('Starting experiment')
    lopy_if.exec_no_follow('receiver.run_one_round()')
    a_pdr = lopy_if.follow(timeout=None)
    round_stats['a_pdr'] = int(a_pdr)
    print('Experiment done. Stats: %s'%(str(round_stats)))

def stop_experiment(sock, addr):
    rslt_pkt = 'rslt'\
                +chr(round_stats['a_pdr'])\
                +chr(-round_stats['a_pwr'])\
                +chr(-round_stats['b_pwr'])
    print('All done. Reporting: %s'%rslt_pkt)
    sock.sendto(rslt_pkt, addr)
    # Round is done

print('Done setup, waiting clients')
while True:
    # Packet structure is 
    # 'next' | CFG_ID (2B) | SF | BW_idx | CR_idx | PW
    # In total 10B
    rcvd, addr = s.recvfrom(4)
    if len(rcvd) < 4:
        print('Length is wrong')
        continue
    # Run the corresponding function
    try:
        {'init': prepare_power_eval,
         'strt': start_experiment,
         'fini': stop_experiment}[str(rcvd[:4], 'utf-8')](s, addr)
    except KeyError:
        continue

