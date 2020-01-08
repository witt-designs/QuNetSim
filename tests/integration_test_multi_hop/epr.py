from cqc.pythonLib import CQCConnection
import sys
import time

sys.path.append("../..")
from backends.cqc_backend import CQCBackend
from components.host import Host
from components.network import Network
from objects.qubit import Qubit

MAX_WAIT = 20

def main():
    backend = CQCBackend()
    network = Network.get_instance()
    nodes = ["Alice", "Bob", "Eve", "Dean"]
    network.start(nodes, backend)
    hosts = {'alice': Host('Alice', backend),
             'bob': Host('Bob', backend),
             'eve': Host('Eve', backend)}

    network.delay = 0

    # A <-> B
    hosts['alice'].add_connection('Bob')
    hosts['bob'].add_connection('Alice')

    # B <-> E
    hosts['bob'].add_connection('Eve')
    hosts['eve'].add_connection('Bob')

    hosts['alice'].start()
    hosts['bob'].start()
    hosts['eve'].start()

    for h in hosts.values():
        network.add_host(h)

    q_id = hosts['alice'].send_epr(hosts['eve'].host_id)

    i = 0
    q1 = None
    q2 = None
    while i < MAX_WAIT and q1 is None:
        q1 = hosts['alice'].get_epr(hosts['eve'].host_id, q_id)
        i += 1
        time.sleep(1)

    assert q1 != None

    i = 0
    while i < MAX_WAIT and q2 is None:
        q2 = hosts['eve'].get_epr(hosts['alice'].host_id, q_id)
        i += 1
        time.sleep(1)

    assert q2 != None
    assert q1.measure() == q2.measure()
    print("All tests succesfull!")
    network.stop(True)
    exit()


if __name__ == '__main__':
    main()