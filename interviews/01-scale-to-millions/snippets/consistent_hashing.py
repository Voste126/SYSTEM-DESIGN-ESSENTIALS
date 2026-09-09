"""
Consistent Hashing & Database Sharding Simulation
Chapter 01: Scale from Zero to Millions of Users

Demonstrates why naive modulo sharding (hash(k) % N) causes a massive
cache/data invalidation cascade when adding a shard node, and how
Consistent Hashing with virtual nodes solves this by remapping only K/N keys.
"""

import hashlib
import bisect


def naive_shard(key: str, num_shards: int) -> int:
    """Naive modulo sharding: hash(key) % N"""
    digest = int(hashlib.md5(key.encode('utf-8')).hexdigest(), 16)
    return digest % num_shards


class ConsistentHashRing:
    """Consistent Hash Ring with virtual nodes."""

    def __init__(self, nodes=None, replicas: int = 100):
        self.replicas = replicas
        self.ring = []          # Sorted list of hash values
        self.node_map = {}      # hash -> physical node name

        if nodes:
            for node in nodes:
                self.add_node(node)

    def _hash(self, val: str) -> int:
        return int(hashlib.md5(val.encode('utf-8')).hexdigest(), 16)

    def add_node(self, node: str):
        for i in range(self.replicas):
            v_key = f"{node}#vnode{i}"
            h = self._hash(v_key)
            bisect.insort(self.ring, h)
            self.node_map[h] = node

    def remove_node(self, node: str):
        for i in range(self.replicas):
            v_key = f"{node}#vnode{i}"
            h = self._hash(v_key)
            idx = bisect.bisect_left(self.ring, h)
            if idx < len(self.ring) and self.ring[idx] == h:
                del self.ring[idx]
                del self.node_map[h]

    def get_node(self, key: str) -> str:
        if not self.ring:
            return None
        h = self._hash(key)
        idx = bisect.bisect_right(self.ring, h)
        if idx == len(self.ring):
            idx = 0  # wrap around the ring
        return self.node_map[self.ring[idx]]


def run_simulation():
    print("=== Database Sharding Resharding Simulation ===")
    num_keys = 10_000
    sample_keys = [f"user_session_{i}" for i in range(num_keys)]

    # 1. Naive Modulo Sharding Test
    initial_shards = 4
    new_shards = 5

    initial_mapping = {k: naive_shard(k, initial_shards) for k in sample_keys}
    new_mapping = {k: naive_shard(k, new_shards) for k in sample_keys}

    remapped_count = sum(1 for k in sample_keys if initial_mapping[k] != new_mapping[k])
    percent_remapped = (remapped_count / num_keys) * 100
    print(f"\n[Naive Modulo Sharding] 4 -> 5 Shards:")
    print(f"  Keys remapped: {remapped_count}/{num_keys} ({percent_remapped:.1f}%)")
    print(f"  Result: Almost ALL data moves. Devastating cache misses and DB migration cost!")

    # 2. Consistent Hash Ring Test
    ring = ConsistentHashRing(nodes=["db-shard-1", "db-shard-2", "db-shard-3", "db-shard-4"], replicas=150)
    c_initial = {k: ring.get_node(k) for k in sample_keys}

    ring.add_node("db-shard-5")
    c_new = {k: ring.get_node(k) for k in sample_keys}

    c_remapped = sum(1 for k in sample_keys if c_initial[k] != c_new[k])
    c_percent = (c_remapped / num_keys) * 100
    print(f"\n[Consistent Hashing] 4 -> 5 Shards:")
    print(f"  Keys remapped: {c_remapped}/{num_keys} ({c_percent:.1f}%)")
    print(f"  Expected theoretical remapping (1/N = 1/5): 20.0%")
    print(f"  Result: Only ~{c_percent:.1f}% of keys moved to the new node. Minimal disruption!")


if __name__ == "__main__":
    run_simulation()
