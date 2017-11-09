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
    config_str = "{{'sf':{0}, 'bw_idx':{1}, 'cr_idx':{2}}}"\
                            .format(sf, bw_idx, CR_idx)
    return config_str


# Open serial connection to LoPy
if len(sys.argv) < 2:
    print('Usage: server.py <tty>')
    sys.exit(1)

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

round_stats = {'a_pwr':0, 'b_pwr':0, 'a_pdr':0, 'b_pdr':0}

def init_lopy(lopy_if, config):
    print('Rebooting')
    lopy_if.hard_reboot()
    sleep(1)
    # Import functions
    print('Importing functions')
    output = lopy_if.exec_('import receiver')
    lopy_if.exec_('receiver.setup(%s)'%config)
    print('Receiver ready', output)

def prepare_power_eval(pld, sock, addr):
    """
    First step, receive probe packets from the senders and
    measure their RX power.
    """
    print('Power eval')
    [sf,bw_idx,cr_idx,a_pw,b_pw] = pld[:5]
    cfg_str = write_configuration(sf,bw_idx,cr_idx)
    print('Starting power eval with config %s', cfg_str)
    # Prepare receiver for a new round. Blocking, <2s
    init_lopy(lopy_if, cfg_str)
    # Put receiver node into eval tx mode
    lopy_if.exec_no_follow('receiver.eval_tx_power()')
    # Read average values from receiver. Blocking, takes 20s
    output = lopy_if.follow(timeout=None)
    print('Eval output: %s'%str(output))
    # Store these values in global variables
    round_stats['a_pwr'] = int(float(output[0].split()[0]))
    round_stats['b_pwr'] = int(float(output[0].split()[1]))
    print(round_stats)

def start_experiment(pld, sock, addr):
    [sf,bw_idx,cr_idx,a_pw,b_pw] = pld[:5]
    #cfg_str = write_configuration(sf,bw_idx,cr_idx)
    # Tell RX to signal start exp to the two senders.
    print('Starting experiment')
    lopy_if.exec_no_follow('receiver.run_one_round()')
    pdrs = lopy_if.follow(timeout=None)
    print(pdrs)
    round_stats['a_pdr'] = int(pdrs[0].split()[0])
    round_stats['b_pdr'] = int(pdrs[0].split()[1])
    print('Experiment done. Stats: %s'%(str(round_stats)))

def stop_experiment(pld, sock, addr):
    rslt_pkt = 'rslt'\
                +chr(round_stats['a_pdr'])\
                +chr(round_stats['b_pdr'])\
                +chr(-round_stats['a_pwr'])\
                +chr(-round_stats['b_pwr'])
    sleep(5)
    print('All done. Reporting: %s to %s'%(rslt_pkt, str(addr)))
    sock.sendto(bytearray(rslt_pkt, 'utf-8'), addr)
    # Round is done

s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.setblocking(False)
s.bind(('', PORT))

print('Done setup, waiting clients')
while True:
    # Packet structure is 
    # 'next' | CFG_ID (2B) | SF | BW_idx | CR_idx | PW
    # In total 10B
    try:
        rcvd, addr = s.recvfrom(20)
    except socket.error:
        sleep(0.5)
        continue
    print('Received')
    print(str(rcvd), len(rcvd))
    if len(rcvd) < 4:
        print('Length is wrong')
        sleep(0.5)
        continue
    # Run the corresponding function
    try:
        {'init': prepare_power_eval,
         'strt': start_experiment,
         'fini': stop_experiment}[str(rcvd[:4], 'utf-8')](rcvd[4:], s, addr)
    except KeyError:
        print('Unknown packet: %s'%rcvd[:4])
        continue

