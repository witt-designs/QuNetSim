from backends.RWLock import RWLock

STORAGE_LIMIT_ALL = 1
STORAGE_LIMIT_PER_HOST = 2
STORAGE_LIMIT_INDIVIDUALLY_PER_HOST = 3


class QuantumStorage(object):
    """
    An object which stores qubits.
    """

    def __init__(self):
        # _host_dict stores host_id -> array with qubits of the host.
        self._host_dict = {}
        # _qubit_dict stores qubit_id -> dict Host_id -> Qubit objects with this id.
        self._qubit_dict = {}
        # _purpose_dict stores qubit_id -> dict Host_id -> Purpose belonging to
        # the Qubit with the same Host and ID.
        self._purpose_dict = {}
        self._storage_mode = STORAGE_LIMIT_INDIVIDUALLY_PER_HOST
        self._storage_limits_per_host = {}
        self._amount_qubits_stored_per_host = {}
        self._default_storage_limit_per_host = -1
        self._storage_limit = -1
        self._amount_qubit_stored = 0
        # read write lock, for threaded access
        self.lock = RWLock()

    def __str__(self):
        out = ""
        out += "Quantum storage with the properties:\nstorage mode: %d\nstorage limit: %d\n" % (
            self._storage_mode, self._storage_limit)
        out += "Host dictionary is:\n"
        out += "; ".join([str(key) + ":" + str([v.id for v in value])
                          for key, value in self._host_dict.items()])
        out += "\n"
        out += "Qubit dictionary is:\n"
        out += "; ".join([str(key) + ":" + str(value)
                          for key, value in self._qubit_dict.items()])
        out += "\n"
        out += "Purpose dictionary is:\n"
        out += "; ".join([str(key) + ":" + str(value)
                          for key, value in self._purpose_dict.items()])
        out += "\n"
        return out

    @property
    def storage_limit(self):
        return self._storage_limit

    @property
    def storage_limit_mode(self):
        return self._storage_mode

    @property
    def amount_qubits_stored(self):
        return self._amount_qubit_stored

    # TODO: refactor to use setter decorator
    def set_storage_limit_mode(self, new_mode):
        self._storage_mode = new_mode

    # TODO: refactor to use setter decorator
    def set_storage_limit(self, new_limit, host_id=None):
        """
        Set a new storage limit for the storage. The implementations depends on
        the storage mode.

        Args:
            new_limit (int): The new max amount of qubit.
            host_id (String): optional, if given, and the storage mode is
                            STORAGE_LIMIT_INDIVIDUALLY_PER_HOST, the limit is only
                            set for this specific host.
        """
        if self._storage_mode == STORAGE_LIMIT_ALL:
            self._storage_limit = new_limit
        elif self._storage_mode == STORAGE_LIMIT_PER_HOST:
            self._storage_limit = new_limit
        elif self._storage_mode == STORAGE_LIMIT_INDIVIDUALLY_PER_HOST:
            if host_id is None:
                self._default_storage_limit_per_host = new_limit
                for id_ in list(self._storage_limits_per_host):
                    self._storage_limits_per_host[id_] = new_limit
            else:
                self._storage_limits_per_host[host_id] = new_limit
        else:
            raise ValueError(
                "Internal Value Error, this storage mode does not exist.")

    def reset_storage(self):
        """
        Reset the quantum storage.
        """
        pass

    def release_storage(self):
        """
        Releases all qubits in this storage. The storage is not
        usable anymore after this function has been called.
        """
        self.lock.acquire_write()
        for q in self._qubit_dict.values():
            for ele in q.values():
                ele.release()
        # do not release write, storage not usable anymore

    def check_qubit_from_host_exists(self, from_host_id, purpose=None):
        """
        Check if a qubit from a host exists in this quantum storage.

        Args:
            from_host_id (str): The host id of the host from which the qubit is from.
            purpose (String): Optional, purpose of the qubit which should exist.

        Returns:
            True, if such a qubit is in the storage, false if not.
        """
        self.lock.acquire_write()
        if from_host_id not in self._host_dict:
            self.lock.release_write()
            return False
        for q in self._host_dict[from_host_id]:
            if self._check_qubit_in_system(q, from_host_id, purpose):
                self.lock.release_write()
                return True
        self.lock.release_write()
        return False

    def change_qubit_id(self, from_host_id, new_id, old_id=None):
        """
        Changes the ID of a qubit. If the ID is not given, a random
        qubit which is from a host is changed to the new id.
        """
        new_id = str(new_id)
        self.lock.acquire_write()
        if old_id is not None:
            old_id = str(old_id)
            qubit, purp = self._pop_qubit_with_id_and_host_from_qubit_dict(
                old_id, from_host_id)
            if qubit is not None:
                qubit.id = new_id
                self._add_qubit_to_qubit_dict(qubit, purp, from_host_id)
                self.lock.release_write()
                return old_id
        else:
            if from_host_id in self._host_dict and self._host_dict[from_host_id]:
                qubit = self._host_dict[from_host_id][0]
                old_id = qubit.id
                _, purp = self._pop_qubit_with_id_and_host_from_qubit_dict(
                    old_id, from_host_id)
                qubit.id = new_id
                self._add_qubit_to_qubit_dict(qubit, purp, from_host_id)
                self.lock.release_write()
                return old_id
        self.lock.release_write()
        return None

    def add_qubit_from_host(self, qubit, purpose, from_host_id):
        """
        Adds a qubit which has been received from a host.

        Args:
            qubit (Qubit): qubit which should be stored.
            from_host_id (String): Id of the Host from whom the qubit has
                             been received.
            purpose (String): Purpose of the Qubit, for example EPR or data.
        """

        self.lock.acquire_write()
        if self._check_qubit_in_system(qubit, from_host_id, purpose=purpose):
            print(self)
            raise ValueError("Qubit with these parameters already in storage!")
        if from_host_id not in self._host_dict:
            self._add_new_host(from_host_id)
        if not self._increase_qubit_counter(from_host_id):
            qubit.release()
            self.lock.release_write()
            return

        self._host_dict[from_host_id].append(qubit)
        self._add_qubit_to_qubit_dict(qubit, purpose, from_host_id)
        self.lock.release_write()

    def get_all_qubits_from_host(self, from_host_id, purpose=None):
        """
        Get all Qubits from a specific host id.
        These qubits are not removed from storage!
        """
        out = []
        self.lock.acquire_write()
        if from_host_id in self._host_dict:
            for q in self._host_dict[from_host_id]:
                if self._check_qubit_in_system(q, from_host_id, purpose):
                    out.append(q)
            self.lock.release_write()
            return out
        self.lock.release_write()
        return []

    def get_qubit_from_host(self, from_host_id, q_id=None, purpose=None):
        """
        Returns next qubit which has been received from a host. If id is
        given, the exact qubit with the id is returned, or None if it does not exist.
        The qubit is removed from the quantum storage.

        Args:
            from_host_id (String): Host id from who the qubit has been received.
            q_id (String): Optional Id, to return the exact qubit with the Id.
            purpose (String): Optional, purpose of the Qubit.

        Returns:
            If such a qubit exists, it returns the qubit. Otherwise, None
            is returned.
        """
        self.lock.acquire_write()
        if q_id is not None:
            qubit = self._pop_qubit_with_id_and_host_from_qubit_dict(q_id, from_host_id, purpose=purpose)
            if qubit is not None:
                qubit, purp = qubit
                if from_host_id not in self._host_dict or \
                        qubit not in self._host_dict[from_host_id]:
                    # Qubit with the ID exists, but does not belong to the host requested
                    self._add_qubit_to_qubit_dict(qubit, purp, from_host_id)
                    return None
                self._host_dict[from_host_id].remove(qubit)
                self._decrease_qubit_counter(from_host_id)
            self.lock.release_write()
            return qubit

        if from_host_id not in self._host_dict:
            self.lock.release_write()
            return None
        if self._host_dict[from_host_id]:
            qubit = self._host_dict[from_host_id].pop(0)
            out = self._pop_qubit_with_id_and_host_from_qubit_dict(qubit.id, from_host_id, purpose=purpose)
            if out is not None:
                self._decrease_qubit_counter(from_host_id)
                self.lock.release_write()
                return out[0]
            self._host_dict[from_host_id].append(qubit)
        self.lock.release_write()
        return None

    def _pop_qubit_with_id_and_host_from_qubit_dict(self, q_id, from_host_id, purpose=None):
        def _pop_purpose_from_purpose_dict(q_id, from_host_id):
            if q_id not in self._purpose_dict:
                return None
            pur = self._purpose_dict[q_id].pop(from_host_id, None)
            if pur is not None:
                if not self._purpose_dict[q_id]:
                    del self._purpose_dict[q_id]
                return pur
            return None

        purp = _pop_purpose_from_purpose_dict(q_id, from_host_id)
        if purp is not None:
            if purpose is None or purpose == purp:
                qubit = self._qubit_dict[q_id].pop(from_host_id, None)
                if qubit is not None:
                    if not self._qubit_dict[q_id]:
                        del self._qubit_dict[q_id]
                return qubit, purp
            else:
                if q_id not in self._purpose_dict:
                    self._purpose_dict[q_id] = {}
                self._purpose_dict[q_id][from_host_id] = purp
        return None

    def _add_qubit_to_qubit_dict(self, qubit, purpose, from_host_id):
        def _add_purpose_to_purpose_dict(purpose, id, from_host_id):
            if id not in self._purpose_dict:
                self._purpose_dict[id] = {}
            self._purpose_dict[id][from_host_id] = purpose

        if qubit.id not in self._qubit_dict:
            self._qubit_dict[qubit.id] = {}
        self._qubit_dict[qubit.id][from_host_id] = qubit
        _add_purpose_to_purpose_dict(purpose, qubit.id, from_host_id)

    def _add_new_host(self, host_id):
        if host_id not in self._host_dict:
            self._host_dict[host_id] = []
            if host_id not in self._storage_limits_per_host:
                self._storage_limits_per_host[host_id] = self._default_storage_limit_per_host
            self._amount_qubits_stored_per_host[host_id] = 0

    def _check_qubit_in_system(self, qubit, from_host_id, purpose=None):
        """
        True if qubit with same parameters already in the systems
        """
        if qubit.id in self._qubit_dict and \
                from_host_id in self._qubit_dict[qubit.id]:
            if purpose is None or (purpose == self._purpose_dict[qubit.id][from_host_id]):
                return True
        return False

    def _check_memory_limits(self, host_id):
        """
        Checks if another qubit can be added to the storage.

        Args:
            host_id (String): The host_id the qubit should be added to.

        Returns:
            True if no storage limit has been reached, False if a memory
            limit has occurred.
        """
        if self._storage_mode == STORAGE_LIMIT_ALL:
            if self._storage_limit == -1:
                return True
            if self._storage_limit <= self._amount_qubit_stored:
                return False
            else:
                return True
        elif self._storage_mode == STORAGE_LIMIT_PER_HOST:
            if self._storage_limit == -1:
                return True
            if self._storage_limit <= self._amount_qubits_stored_per_host[host_id]:
                return False
            else:
                return True
        elif self._storage_mode == STORAGE_LIMIT_INDIVIDUALLY_PER_HOST:
            if self._storage_limits_per_host[host_id] == -1:
                return True
            if self._storage_limits_per_host[host_id] <= self._amount_qubits_stored_per_host[host_id]:
                return False
            else:
                return True
        else:
            raise ValueError(
                "Internal Value Error, this storage mode does not exist.")

    def _increase_qubit_counter(self, host_id):
        """
        Checks if the qubit counter can be increased, because of memory limits,
        and increases the counter.

        Args:
            host_id (String): From who the qubit comes from.

        Returns:
            True, if the counter could be increased, False if not.
        """
        if not self._check_memory_limits(host_id):
            return False
        self._amount_qubits_stored_per_host[host_id] += 1
        self._amount_qubit_stored += 1
        return True

    def _decrease_qubit_counter(self, host_id):
        """
        Checks if the qubit counter can be decreased
        and decreases the counter.

        Args:
            host_id (String): From who the qubit comes from.

        Returns:
            True, if the counter could be decreased, False if not.
        """
        if self._amount_qubits_stored_per_host[host_id] <= 0 or \
                self._amount_qubit_stored <= 0:
            return False
        self._amount_qubits_stored_per_host[host_id] -= 1
        self._amount_qubit_stored -= 1
