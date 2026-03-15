# fake/fake_funcs.py

def


from time import sleep

def query(i: int) -> str:
    sleep(2)
    return f"query result{i}"


def answer(i: int) -> str:
    query_result = query(i)
    sleep(2)
    return f"answer result{i}: {query_result}"
