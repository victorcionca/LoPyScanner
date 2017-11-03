"""
This thread manages the LoPy board and reports to the master.
"""
import socket
from lopy_serial_if import Pyboard
from time import sleep


class SenderManager(threading.Thread):
    def __init__(self, port, node_id, leader=False, first_run=False):
        """
        Params:
        port        -- serial port of LoPy board
        node_id     -- id associated to LoPy board (string).
        leader      -- True if this is the node whose PDR is tested.
        first_run   -- Set to true to enable initial configuration,
                       mainly used for copying code to Flash only once.
        """
        super().__init__()
        self.port = port
        self.node_id = node_id
        self.config = None
        self.offset = None
        self.txd_packets = 0
        self.leader = leader

        self.lopy_if = Pyboard(self.port)

        if first_run:
            # Only copy code to flash the first time, to save the flash
            print('Uploading sender code')
            self.lopy_if.put('/flash/sender.py', 'sender.py')

    def setup(self, config_str, offset=0):
        self.config = config_str
        self.offest = offset

        # Soft reboot to get the receiver code loaded
        print('Rebooting')
        self.lopy_if.hard_reboot()
        sleep(1)
        # Import functions
        print('Importing functions')
        output = self.lopy_if.exec_('import sender')
        print('Sender ready', output)

    def eval_tx_power(self):
        self.lopy_if.exec_('sender.eval_tx_power(%s,%s)'
                                    %(self.config, self.node_id))

    def run(self):
        """
        Runs one round with the current configuration
        """
        self.lopy_if.exec_no_follow('sender.run_one_round(%s, %s, %d)'
                                    %(self.config, self.node_id, self.offset))
        output = lopy_if.follow(timeout=None)
        self.txd_packets = int(output.split()[-1])
        if self.leader:
            # Before we finish, tell the receiver that the round is over
            self.lopy_if.exec_no_follow('sender.complete_round(%s)'%(self.config))
        # Done
