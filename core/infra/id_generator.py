# core/infra/id_generator.py

import uuid


class IdGenerator:
    def new_session_id(self) -> str:
        return str(uuid.uuid4())
