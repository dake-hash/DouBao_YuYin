"""
audio_buffer.py — 线程安全的环形缓冲区

P4: 使用 collections.deque + threading.Lock 实现高性能环形缓冲区，
支持音频采集线程（写）和 WebSocket 发送线程（读）并发访问。
"""

import threading
from collections import deque


class AudioBuffer:
    """线程安全的字节环形缓冲区。

    适用于单生产者（音频回调）单消费者（WebSocket 发送）场景。
    所有读写操作均通过 threading.Lock 保护。

    属性:
        available_bytes: 当前缓冲区中的可用字节数
        is_empty: 缓冲区是否为空
    """

    def __init__(self, max_size: int = 1024 * 1024) -> None:
        """初始化缓冲区。

        Args:
            max_size: 最大字节数（默认 1 MB）。超出时丢弃最旧的数据。
        """
        self._buf: deque[bytes] = deque()
        self._max_size = max_size
        self._size = 0              # 缓存的字节计数，避免每次 sum
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def write(self, chunk: bytes) -> None:
        """追加一个数据块到缓冲区末尾。

        如果缓冲区已满（total + chunk > max_size），从头部丢弃旧数据。

        Args:
            chunk: 要写入的字节数据。
        """
        with self._lock:
            chunk_len = len(chunk)
            # 丢弃旧数据直到有空间
            while self._size + chunk_len > self._max_size and self._buf:
                old = self._buf.popleft()
                self._size -= len(old)
            self._buf.append(chunk)
            self._size += chunk_len

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def read(self, n_bytes: int) -> bytes:
        """读取最多 n_bytes 字节的数据。

        如果缓冲区中数据不足，返回所有可用的数据。

        Args:
            n_bytes: 要读取的字节数。

        Returns:
            读取到的字节数据（可能少于请求量）。
        """
        with self._lock:
            if not self._buf:
                return b""
            return self._read_locked(min(n_bytes, self._size))

    def read_all(self) -> bytes:
        """读取缓冲区中的所有数据并清空。"""
        with self._lock:
            if not self._buf:
                return b""
            data = self._read_locked(self._size)
            return data

    def _read_locked(self, n_bytes: int) -> bytes:
        """内部方法：在已持有锁的情况下读取 n_bytes 字节。"""
        parts: list[bytes] = []
        remaining = n_bytes
        while remaining > 0 and self._buf:
            chunk = self._buf[0]
            if len(chunk) <= remaining:
                self._buf.popleft()
                self._size -= len(chunk)
                parts.append(chunk)
                remaining -= len(chunk)
            else:
                parts.append(chunk[:remaining])
                self._buf[0] = chunk[remaining:]
                self._size -= remaining
                remaining = 0
        return b"".join(parts)

    # ------------------------------------------------------------------
    # 管理
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """清空缓冲区。"""
        with self._lock:
            self._buf.clear()
            self._size = 0

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @property
    def available_bytes(self) -> int:
        """当前缓冲区的可用字节数。"""
        return self._size

    @property
    def is_empty(self) -> bool:
        """缓冲区是否为空。"""
        return self._size == 0
