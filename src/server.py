import socket
import pickle
import logging

from src import configure as config
from src.consistenthashing import ConsistentHashing
from src import utils

config = config.config()

"""
The server is always listening to the client. It needs to detect if the client is alive.
"""


class CacheServer:
    def __init__(self, num_virtual_replicas=5, expire=0, log_filename='cache.csv', reconstruct=False):
        """
        :param[int] num_virtual_replicas: number of virtual replicas of each cache server
        :param[int] expire: expiration time for keys in seconds.
        """
        self.num_virtual_replicas = num_virtual_replicas
        self.expire = expire
        self.ring = ConsistentHashing()

        self.ADDRESS = config.ADDRESS
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(self.ADDRESS)
        self.clients = {}
        self.start()

        # Cache stats
        self.cache_hits = 0
        self.query_count = 0

        # Communication configuration
        self.HEADER_LENGTH = config.HEADER_LENGTH
        self.FORMAT = config.FORMAT
        self.LISTEN_CAPACITY = config.LISTEN_CAPACITY

        logging.basicConfig(filename=log_filename, filemode='w', level=0)
        logging.info(pickle.dumps((num_virtual_replicas, expire)))

    def reconstruct_from_log(self):
        """ Usage:
            Start the server.
            Spawn the clients.
            Then ask the server to reconstruct from log file
        """
        pass

    def start(self):
        # Listen
        print("Starting server at {}:{}".format(*self.ADDRESS))
        self.server_socket.listen(config.LISTEN_CAPACITY)

    def spawn(self):
        """
        Listens for new connections. And add it as a cache server.
        """
        while True:
            client_socket, client_address = self.server_socket.accept()

            client_id = len(self.clients)
            self.clients[client_id] = (client_socket, client_address)

            utils.send_message(client_id, client_socket, self.HEADER_LENGTH, self.FORMAT)
            self.ring.add_node(client_socket, self.num_virtual_replicas)
            break

        print("Spawned a client at {}:{}".format(*client_address))

    def send_receive(self, message, client_socket):
        print("Sending client message: {}".format(message))
        response = utils.send_receive_ack(message, client_socket, self.HEADER_LENGTH, self.FORMAT)
        print("Response received: {}\n".format(response))
        return response

    def set(self, key, value):
        """
        Set or update the value of key from the cache. Also updates the LRU cache for already existing key or (key, value)
        :return: bool value indicating if the operation was successful or not.
        """
        # Get the address of the server containing the key
        client_socket, client_address = self._get_server_for_key(key)
        response = self.send_receive(("set", key, value), client_socket)
        logging.info(("set", key, value))  # TODO: Gotta be async and batched
        return True if response else False

    def get(self, key):
        """
        Get the value of key from the cache
        :return: corresponding value for the key
        """
        # Get the address of the server containing the key
        client_socket, client_address = self._get_server_for_key(key)
        response = self.send_receive(("get", key), client_socket)
        logging.info(("get", key))

        self.query_count += 1
        self.cache_hits += (response != False)

        return response

    def gets(self, keys):
        """
        Gets the values of keys from the cache. Same as get but avoids expensive network calls.
        If you want two keys which are on different server, gets is same as get or a bit slower.
        :return [list of values]: corresponding values for the keys
        """
        pass

    def delete(self, key):
        """
        Get the value of key from the cache
        :return: corresponding value for the key
        """
        # Get the address of the server containing the key
        client_socket, client_address = self._get_server_for_key(key)
        response = self.send_receive(("del", key), client_socket)
        logging.info(("del", key))
        return response

    def increment(self, key):
        """
        Increment value corresponding to the key in a thread-safe manner.
        :return: boolean indicating if the operation was successful or not.
        """
        return self.add(key, 1)

    def decrement(self, key):
        """
        Decrement value corresponding to the key in a thread-safe manner.
        :return: boolean indicating if the operation was successful or not.
        :rtype: bool
        """
        return self.add(key, -1)

    def add(self, key, diff):
        """
        Add diff to the value corresponding to key in a thread safe manner.
        :param diff: the amount to be added to the value of key
        :return: boolean indicating if the operation was successful or not.
        :rtype: bool
        """
        client_socket, client_address = self._get_server_for_key(key)
        response = self.send_receive(("add", key, diff), client_socket)
        logging.info(("add", key, diff))
        return response

    def _get_server_for_key(self, key):
        """
        :return: client_socket for the given key
        """
        return self.ring.get_node(key), None

    def _delist_unavailable_server(self, client_socket):
        """
        The health check metrics found an unavailable server. It should be removed from the server space.
        :return: None
        """
        self.ring.remove_node(client_socket)

    def stats(self):
        """
        Prints some of the important stats like hits, misses and total query counts
        :return: None
        """
        print("Total queries: ".format(self.query_count))
        print("Cache hits   : {}\t{.2f}".format(self.cache_hits, self.cache_hits / self.query_count))
        print("Cache miss   : {}\t{.2f}".format(self.cache_hits, self.cache_hits / self.query_count))


if __name__ == '__main__':
    pass
