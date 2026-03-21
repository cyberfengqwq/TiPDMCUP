# core/user.py


from agent.pipeline import Agent


class User:
    """
    Description:
        用户类，存放用户个人信息，以及存放用户对应的 Agent
    """

    def __init__(self, name: str, psw: str, session_id: str) -> None:
        self.name: str = name
        self.__psw = psw
        self.__session_id = session_id

        self.agent = Agent()

    @property
    def get_psw(self) -> str:
        return self.__psw

    @property
    def get_session_id(self) -> str:
        return self.__session_id
