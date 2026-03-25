# core/stores/base_json_store.py

import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any


class BaseJsonStore:
    """
    基础的 Json 文件读写类
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = Path(file_path)
        self._lock = RLock()

    def read_json(self) -> Any:
        """读取 Json 文件

        Returns:
            读取之后返回的 Json 文件对象
        """
        with self._lock:
            if not self.file_path.exists():
                return []
            with self.file_path.open("r", encoding="utf-8") as f:
                return json.load(f)

    def write_json_atomic(self, data: Any) -> None:
        """原子性写入 Json 文件

        Args:
            data: Any 写入的 Json 文件对象

        Raise:
            e   : 写入错误

        """
        with self._lock:
            temp_dir: Path = self.file_path.parent / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            fd, temp_str = tempfile.mkstemp(
                dir=str(temp_dir), prefix=f"{self.file_path.stem}_", suffix=".tmp"
            )
            temp_path = Path(temp_str)

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    f.flush()
                    os.fsync(f.fileno())
                temp_path.replace(self.file_path)
            except Exception as e:
                temp_path.unlink(missing_ok=True)
                raise e
            finally:
                temp_path.unlink(missing_ok=True)
