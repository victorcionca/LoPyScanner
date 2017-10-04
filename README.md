# LoPy Scanner

Scan all the possible transmission configurations of LoRa with LoPy hardware.
Record PRR (Packet Reception Rate), SNR and received Spreading Factor.

Python3, mycroPython

## Components

* 2x LoPy, one will be sender the other receiver
* 2x network connected gateways (e.g. Raspberry Pi)


## Architecture

* LoRa sender and receiver
* controllers: client and server
* the controllers interface with the LoPy HW over serial; this is inspired by
AmPy: https://github.com/adafruit/ampy
* sender and receiver execute one function, run\_one\_round(configuration)
  * this function configures LoRa with: SF, BW, CR, TXPow
* the client controller generates all the configurations, and for each config:
  * sends the config via UDP to the server controller
  * waits for a defined interval so the receiver is ready
  * tells the sender to execute run\_one\_round
* the server controller waits for the configuration packets, and tells the LoPy to
  * first cancel any running execution
  * save the current results to Flash, download them locally, delete from Flash
  * reboot
  * run\_one\_round with received configuration.

## Quirks

* very little memory available on LoPy, so used separate Arrays instead of lists
to save the packet statistics.
