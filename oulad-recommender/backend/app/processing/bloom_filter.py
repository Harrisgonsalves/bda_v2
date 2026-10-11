"""Small Bloom filter. A positive answer may be a false positive: verify important decisions in MongoDB."""
import hashlib
import math


class BloomFilter:
    def __init__(self, expected_items: int, fp_rate: float = 0.01):
        self.m = max(8, int(-expected_items * math.log(fp_rate) / (math.log(2) ** 2)))
        self.k = max(1, int(self.m / max(expected_items, 1) * math.log(2)))
        self.bits = bytearray((self.m + 7) // 8)

    def _positions(self, item: str):
        h = hashlib.sha256(item.encode()).digest()
        a, b = int.from_bytes(h[:8], "big"), int.from_bytes(h[8:16], "big") | 1
        return [(a + i * b) % self.m for i in range(self.k)]

    def add(self, item: str):
        for p in self._positions(item):
            self.bits[p >> 3] |= 1 << (p & 7)

    def might_contain(self, item: str) -> bool:
        return all(self.bits[p >> 3] & (1 << (p & 7)) for p in self._positions(item))
