"""先備妥整組產物再發佈；寫入失敗恢復上次成功成品。"""
import os
from pathlib import Path
import tempfile

from workbench.library import safe_path


def publish(directory, outputs):
	directory=Path(directory)
	with tempfile.TemporaryDirectory(prefix='.artifact-',dir=directory) as staging:
		ready=[];changed=[]
		for index,(relative,payload) in enumerate(outputs.items()):
			if not isinstance(payload,bytes):raise ValueError('產物必須先序列化為bytes')
			destination=safe_path(directory,relative)
			destination.parent.mkdir(parents=True,exist_ok=True)
			staged=Path(staging)/f'{index}.new';staged.write_bytes(payload)
			backup=None
			if destination.exists():
				backup=Path(staging)/f'{index}.old';backup.write_bytes(destination.read_bytes())
			ready.append((staged,destination,backup))
		try:
			for staged,destination,backup in ready:
				os.replace(staged,destination);changed.append((destination,backup))
		except OSError:
			for destination,backup in reversed(changed):
				if backup is None:destination.unlink()
				else:os.replace(backup,destination)
			raise
