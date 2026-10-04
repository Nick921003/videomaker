import os
import struct
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "video_engine"))
sys.path.insert(0, os.path.join(ROOT, "video_engine", "board"))

import gemini_tts as GT


def wav_bytes(samples, sr=24000, extra=b""):
	data = np.asarray(samples, dtype="<i2").tobytes()
	fmt = struct.pack("<HHIIHH", 1, 1, sr, sr * 2, 2, 16)
	body = b"WAVE" + b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(data)) + data + extra
	return b"RIFF" + struct.pack("<I", len(body)) + body


class TestPcm(unittest.TestCase):
	def test_只取data區塊不把後面的C2PA憑證當聲音(self):
		c2pa = b"C2PA" + struct.pack("<I", 6) + b"\x8d\x05\x80\x04Q\x06"
		pcm, sr = GT.pcm_from_response(wav_bytes([1, 2, 3, -4], extra=c2pa))
		self.assertEqual(sr, 24000)
		self.assertEqual(pcm.tolist(), [1, 2, 3, -4])

	def test_沒有檔頭的原始PCM照讀(self):
		pcm, sr = GT.pcm_from_response(np.asarray([5, -6], dtype="<i2").tobytes())
		self.assertEqual((pcm.tolist(), sr), ([5, -6], 24000))


if __name__ == "__main__":
	unittest.main()
