# core/user.py

import json
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from agent.pipeline import Agent

ROOT_PATH: Path = Path(__file__).cwd().parent
USER_DATA: Path = ROOT_PATH / "user_data"
USER_DATA.mkdir(parents=True, exist_ok=True)


class User:
    """
    Description:
        用户类，存放用户个人信息，以及存放用户对应的 Agent
    """

    def __init__(self, name: str, psw: str, session_id: str) -> None:
        self.name: str = name
        self.__psw: str = generate_password_hash(psw)
        self.__session_id: str = session_id

        self.agent = Agent()
        self.dir_path: Path = USER_DATA / session_id

    @property
    def get_psw(self) -> str:
        return self.__psw

    @property
    def get_session_id(self) -> str:
        return self.__session_id

    def change_psw(self, new_psw: str) -> bool:
        """更改密码
        Args:
            new_psw: str 新密码

        Returns:
            False: 新密码与旧密码一致
            True:  新密码与旧密码不一致
        """
        new_psw_hash: str = generate_password_hash(new_psw)
        if self.__psw == new_psw_hash:
            print("新密码与旧密码一致！")
            return False

        self.__psw = new_psw_hash
        return True

    def save_data_to_json(self) -> None:
        user_file: dict[str, str] = {
            "name": self.name,
            "password": self.__psw,
            "session_id": self.__session_id,
        }
        file_path: Path = self.dir_path / f"{self.__session_id}_data.json"
        with file_path.open("w", encoding="utf-8") as f:
            json.dump(user_file, f, ensure_ascii=False, indent=4)
