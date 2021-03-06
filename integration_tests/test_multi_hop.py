import unittest
import time

from backends.eqsn_backend import EQSNBackend
from components.host import Host
from objects.qubit import Qubit
from components.network import Network

network = Network.get_instance()
hosts = None


# @unittest.skip('')
class TestTwoHop(unittest.TestCase):
    sim_network = None
    network = None
    hosts = None
    MAX_WAIT = 20

    @classmethod
    def setUpClass(cls):
        global network
        global hosts
        nodes = ["Alice", "Bob", "Eve"]
        backend = EQSNBackend()
        network.start(nodes=nodes, backend=backend)
        hosts = {'alice': Host('Alice', backend),
                 'bob': Host('Bob', backend),
                 'eve': Host('Eve', backend)}
        hosts['alice'].add_connection('Bob')
        hosts['bob'].add_connection('Alice')
        hosts['bob'].add_connection('Eve')
        hosts['eve'].add_connection('Bob')
        hosts['alice'].start()
        hosts['bob'].start()
        hosts['eve'].start()

        for h in hosts.values():
            network.add_host(h)

    @classmethod
    def tearDownClass(cls):
        global network
        global hosts
        network.stop(stop_hosts=True)

    def setUp(self):
        global network
        global hosts
        network.delay = 0.2
        network.packet_drop_rate = 0
        network.use_hop_by_hop = True

        hosts['alice'].delay = 0.1
        hosts['bob'].delay = 0.1
        hosts['eve'].delay = 0.1

        hosts['alice'].set_epr_memory_limit(-1)
        hosts['bob'].set_epr_memory_limit(-1)
        hosts['eve'].set_epr_memory_limit(-1)

        hosts['alice'].set_data_qubit_memory_limit(-1)
        hosts['bob'].set_data_qubit_memory_limit(-1)
        hosts['eve'].set_data_qubit_memory_limit(-1)

        hosts['alice'].empty_classical()
        hosts['bob'].empty_classical()
        hosts['eve'].empty_classical()

    def tearDown(self):
        pass

    # @unittest.skip('')
    def test_send_classical(self):
        hosts['alice'].send_classical(hosts['eve'].host_id, 'testing123')

        messages = hosts['eve'].classical
        i = 0
        while i < TestTwoHop.MAX_WAIT and len(messages) == 0:
            messages = hosts['eve'].classical
            i += 1
            time.sleep(1)

        self.assertTrue(len(messages) > 0)
        self.assertEqual(messages[0].sender, hosts['alice'].host_id)
        self.assertEqual(messages[0].content, 'testing123')

    # @unittest.skip('')
    def test_full_network_routing(self):
        network.use_hop_by_hop = False
        hosts['alice'].send_classical(hosts['eve'].host_id, 'testing123')

        i = 0
        messages = hosts['eve'].classical
        while i < TestTwoHop.MAX_WAIT and len(messages) == 0:
            messages = hosts['eve'].classical
            i += 1
            time.sleep(1)

        self.assertTrue(len(messages) > 0)
        self.assertEqual(messages[0].sender, hosts['alice'].host_id)
        self.assertEqual(messages[0].content, 'testing123')

    # @unittest.skip('')
    def test_epr(self):
        q_id = hosts['alice'].send_epr(hosts['eve'].host_id)

        i = 0
        q1 = None
        q2 = None
        while i < TestTwoHop.MAX_WAIT and q1 is None:
            q1 = hosts['alice'].get_epr(hosts['eve'].host_id, q_id)
            i += 1
            time.sleep(1)

        self.assertIsNotNone(q1)

        i = 0
        while i < TestTwoHop.MAX_WAIT and q2 is None:
            q2 = hosts['eve'].get_epr(hosts['alice'].host_id, q_id)
            i += 1
            time.sleep(1)

        self.assertIsNotNone(q2)
        self.assertEqual(q1.measure(), q2.measure())

    # @unittest.skip('')
    def test_teleport(self):
        q = Qubit(hosts['alice'])
        q.X()

        hosts['alice'].send_teleport(hosts['eve'].host_id, q)
        q2 = None
        i = 0
        while i < TestTwoHop.MAX_WAIT and q2 is None:
            q2 = hosts['eve'].get_data_qubit(hosts['alice'].host_id)
            i += 1
            time.sleep(1)

        self.assertIsNotNone(q2)
        self.assertEqual(q2.measure(), 1)

    # @unittest.skip('')
    def test_superdense(self):
        hosts['alice'].send_superdense(hosts['bob'].host_id, '10')

        messages = hosts['bob'].classical
        i = 0
        while i < TestTwoHop.MAX_WAIT and len(messages) == 0:
            messages = hosts['bob'].classical
            i += 1
            time.sleep(1)

        self.assertTrue(len(messages) > 0)
        self.assertEqual(messages[0].sender, hosts['alice'].host_id)
        self.assertEqual(messages[0].content, '10')

    # @unittest.skip('')
    def test_classical_superdense_combination(self):
        hosts['alice'].send_superdense(hosts['eve'].host_id, '11')
        hosts['alice'].send_classical(hosts['eve'].host_id, 'hello')

        messages = hosts['eve'].classical
        i = 0
        while i < TestTwoHop.MAX_WAIT and len(messages) < 3:
            messages = hosts['eve'].classical
            i += 1
            time.sleep(1)

        self.assertTrue(len(messages) > 0)
        self.assertEqual(messages[0].sender, hosts['alice'].host_id)
        self.assertEqual(messages[0].content, 'hello')
        self.assertEqual(messages[1].sender, hosts['alice'].host_id)
        self.assertEqual(messages[1].content, '11')

    # @unittest.skip('')
    def test_epr_teleport_combination(self):
        q = Qubit(hosts['alice'])
        q.X()

        q_id = hosts['alice'].send_epr(hosts['eve'].host_id)
        hosts['alice'].send_teleport(hosts['eve'].host_id, q)

        q1_epr = None
        q2_epr = None
        q_teleport = None

        i = 0
        while q1_epr is None and i < TestTwoHop.MAX_WAIT:
            q1_epr = hosts['alice'].get_epr(hosts['eve'].host_id, q_id)
            if q1_epr is not None:
                q1_epr = q1_epr
            i += 1
            time.sleep(1)

        i = 0
        while q2_epr is None and i < TestTwoHop.MAX_WAIT:
            q2_epr = hosts['eve'].get_epr(hosts['alice'].host_id, q_id)
            if q2_epr is not None:
                q2_epr = q2_epr
            i += 1
            time.sleep(1)

        i = 0
        while q_teleport is None and i < TestTwoHop.MAX_WAIT:
            q_teleport = hosts['eve'].get_data_qubit(hosts['alice'].host_id)
            if q_teleport is not None:
                q_teleport = q_teleport
            i += 1
            time.sleep(1)

        self.assertIsNotNone(q1_epr)
        self.assertIsNotNone(q2_epr)
        self.assertIsNotNone(q_teleport)
        self.assertEqual(q1_epr.measure(), q2_epr.measure())
        self.assertEqual(q_teleport.measure(), 1)
