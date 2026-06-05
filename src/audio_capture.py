"""
audio_capture.py — 麦克风音频采集

P4: 使用 PyAudio 从系统麦克风采集 PCM 16kHz 16bit 单声道音频，
通过回调写入 AudioBuffer。采集可随时启停，不录音时不占用设备。
"""

import threading
from typing import Optional

import pyaudio

from audio_buffer import AudioBuffer


class AudioCapture:
    """PyAudio 麦克风采集器。

    配置为豆包 ASR 要求的格式：PCM Int16, 16000Hz, 单声道。
    音频数据通过回调写入 AudioBuffer，在 PyAudio 内部线程执行，
    不阻塞主线程。

    用法:
        buf = AudioBuffer()
        cap = AudioCapture(buf)
        cap.start()           # 开始录音
        ...                   # 从 buf 读取数据
        cap.stop()            # 停止录音，释放设备
    """

    # ── 音频配置（与豆包 WebSocket 协议对齐）───────────────────
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    FRAMES_PER_BUFFER = 3200   # 200ms per chunk

    def __init__(self, buffer: AudioBuffer, device_index: Optional[int] = None) -> None:
        """初始化麦克风采集器。

        Args:
            buffer: 音频数据写入的 AudioBuffer 实例。
            device_index: 指定输入设备索引，None 则使用系统默认设备。
        """
        self._buffer = buffer
        self._device_index = device_index

        self._py: Optional[pyaudio.PyAudio] = None
        self._stream: Optional[pyaudio.Stream] = None
        self._running = False
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------

    def start(self) -> None:
        """开始采集音频。

        如果已在运行则忽略。会创建 PyAudio 实例并打开输入流，
        音频回调在 PyAudio 内部线程执行。
        """
        with self._lock:
            if self._running:
                print("[AudioCapture] 已在运行中，忽略重复 start")
                return

            try:
                self._py = pyaudio.PyAudio()
                self._stream = self._py.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    input_device_index=self._device_index,
                    frames_per_buffer=self.FRAMES_PER_BUFFER,
                    stream_callback=self._audio_callback,
                )
                self._running = True
                dev_name = self._get_device_name()
                print(f"[AudioCapture] 已开始录音 (设备: {dev_name})")
            except OSError as e:
                print(f"[AudioCapture] 启动失败: {e}")
                self._cleanup()

    def stop(self) -> None:
        """停止采集，释放麦克风设备。

        关闭音频流并终止 PyAudio。采集停止后缓冲区中剩余数据仍可读取。
        """
        with self._lock:
            if not self._running:
                return
            self._running = False

        print("[AudioCapture] 停止录音")
        self._cleanup()

    def _cleanup(self) -> None:
        """释放 PyAudio 资源。"""
        if self._stream is not None:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except OSError:
                pass
            self._stream = None
        if self._py is not None:
            try:
                self._py.terminate()
            except OSError:
                pass
            self._py = None

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------

    @property
    def is_running(self) -> bool:
        """是否正在采集。"""
        return self._running

    def _get_device_name(self) -> str:
        """获取当前输入设备的名称。"""
        if self._py is not None and self._device_index is not None:
            try:
                info = self._py.get_device_info_by_index(self._device_index)
                return info.get("name", str(self._device_index))
            except OSError:
                pass
        return "默认设备"

    # ------------------------------------------------------------------
    # 回调（在 PyAudio 内部线程执行）
    # ------------------------------------------------------------------

    def _audio_callback(self, in_data, frame_count, time_info, status) -> tuple:
        """PyAudio 流回调 — 将音频块写入 AudioBuffer。

        此方法在 PyAudio 内部线程中被调用，不需要额外线程管理。
        """
        if status:
            print(f"[AudioCapture] 回调状态: {status}")
        try:
            self._buffer.write(in_data)
        except Exception as e:
            print(f"[AudioCapture] 写入缓冲区失败: {e}")
        return (None, pyaudio.paContinue)

    # ------------------------------------------------------------------
    # 析构
    # ------------------------------------------------------------------

    def __del__(self) -> None:
        """确保 PyAudio 资源被释放。"""
        self._cleanup()
