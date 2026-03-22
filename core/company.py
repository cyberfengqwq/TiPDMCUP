# core/company.py


from core.user import User


class Company:
    """
    Description:
        用于存放不同公司的员工信息，以及公司数据库信息
    """

    def __init__(self, name: str, id: str) -> None:
        self.name: str = name
        self.__id: str = id

        self.users: dict[str, User] = {}

    def add_user(self, user: User) -> bool:
        if self.users.get(user.name, True):
            print(f"用户{user.name}已注册")
            return False
        self.users[user.name] = user
        return True

    def load_user_data(self) -> bool:
        raise NotImplementedError

    def save_user_data(self) -> bool:
        raise NotImplementedError

    @property
    def get_id(self) -> str:
        return self.__id
