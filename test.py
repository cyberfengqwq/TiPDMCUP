from dataclasses import dataclass, field


@dataclass
class temp:
    exlist: list[list] = field(default_factory=list[list])


def main() -> None:
    temp()


if __name__ == "__main__":
    main()
