# core/user.py

import json
from pathlib import Path

from werkzeug.security import generate_password_hash

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
        self.file_path: Path = self.dir_path / f"{self.__session_id}_data.json"
        self.user_file_dict: dict[str, str] = {
            "name": self.name,
            "session_id": self.__session_id,
            "password": self.__psw,
        }

    @classmethod
    def init_with_json_file(cls, file_path: Path | str) -> "User":
        """提供由 json 文件来实例化对象的类方法
        Args:
            file_path   : Path | str json 文件路径

        Returns:
            User        : 实例化对象
        """

        file_path = Path(file_path)
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        user = cls(
            name=data["name"], psw=data["password"], session_id=data["session_id"]
        )
        user.user_file_dict = data
        return user

    @property
    def get_psw(self) -> str:
        return self.__psw

    @property
    def get_session_id(self) -> str:
        return self.__session_id

    def change_psw(self, new_psw: str) -> bool:
        """更改密码
        Args:
            new_psw  : str 新密码

        Returns:
            True     : 新密码与旧密码不一致
            False    : 新密码与旧密码一致
        """
        new_psw_hash: str = generate_password_hash(new_psw)
        if self.__psw == new_psw_hash:
            print("新密码与旧密码一致！")
            return False

        self.__psw = new_psw_hash
        return True

    def save_data_to_json(self) -> None:
        """把用户信息保存到 json 文件"""
        with self.file_path.open("w", encoding="utf-8") as f:
            json.dump(self.user_file_dict, f, ensure_ascii=False, indent=4)

    def load_data_from_json(self) -> None:
        """从 json 文件读取用户信息"""
        with self.file_path.open("r", encoding="utf-8") as f:
            self.user_file_dict = json.load(f)

    def verification_psw(self, psw: str) -> bool:
        """验证密码
        Args:
            psw   : str 用户输入的密码
        Returns:
            True  : 用户输入的密码正确
            False : 用户输入的密码错误

        """

        psw_hash: str = generate_password_hash(psw)
        if psw_hash == self.__psw:
            return True
        return False


class AdminUser(User):
    def __init__(self, name: str, psw: str, session_id: str) -> None:
        super().__init__(name, psw, session_id)
