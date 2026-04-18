import argparse
import shutil
from pathlib import Path


PATTERN = "*_content_list_v2.json"


def validate_roots(root_o: Path, root_x: Path) -> None:
    if not root_o.exists():
        raise FileNotFoundError(f"源目录 O 不存在: {root_o}")
    if not root_o.is_dir():
        raise NotADirectoryError(f"源目录 O 必须是目录: {root_o}")

    root_o = root_o.resolve()
    root_x = root_x.resolve()

    if root_o == root_x:
        raise ValueError("O 和 X 不能相同")
    if root_x in [root_o, *root_o.parents]:
        raise ValueError("X 不能是 O 或 O 的上级目录")
    if root_o in [root_x, *root_x.parents]:
        raise ValueError("X 不能位于 O 内部")


def list_a_directories(root_o: Path) -> list[Path]:
    return sorted([path for path in root_o.iterdir() if path.is_dir()])


def find_unique_target_file(dir_a: Path) -> Path:
    matches = [path for path in dir_a.rglob(PATTERN) if path.is_file()]
    if not matches:
        raise FileNotFoundError(f"未找到匹配文件: {dir_a}")
    if len(matches) > 1:
        details = "\n".join(str(path) for path in matches)
        raise RuntimeError(f"目录内匹配到多个目标文件，已中止: {dir_a}\n{details}")
    return matches[0]


def ensure_destination(root_x: Path, source_file: Path, dir_a: Path) -> Path:
    root_x.mkdir(parents=True, exist_ok=True)
    filename = f"{dir_a.name}__{source_file.name}"
    destination = root_x / filename
    if destination.exists():
        raise FileExistsError(f"目标文件已存在，拒绝覆盖: {destination}")
    return destination


def move_one(dir_a: Path, root_x: Path, dry_run: bool) -> tuple[Path, Path]:
    source_file = find_unique_target_file(dir_a)
    destination = ensure_destination(root_x, source_file, dir_a)

    print(f"[A] {dir_a}")
    print(f"  提取: {source_file}")
    print(f"  去向: {destination}")

    if not dry_run:
        shutil.move(str(source_file), str(destination))
        if not destination.exists():
            raise RuntimeError(f"移动后未在目标位置找到文件: {destination}")
        if source_file.exists():
            raise RuntimeError(f"移动后源文件仍存在: {source_file}")

    return source_file, destination


def remove_a_directory(dir_a: Path, dry_run: bool) -> None:
    if dry_run:
        print(f"  dry-run: 未删除 {dir_a}")
        return

    shutil.rmtree(dir_a)
    if dir_a.exists():
        raise RuntimeError(f"删除目录失败: {dir_a}")
    print(f"  已删除: {dir_a}")


def process_root(root_o: Path, root_x: Path, dry_run: bool = True) -> None:
    root_o = root_o.resolve()
    root_x = root_x.resolve()

    validate_roots(root_o, root_x)
    dir_as = list_a_directories(root_o)
    if not dir_as:
        raise FileNotFoundError(f"O 下未找到任何 A 目录: {root_o}")

    success_count = 0
    failure_count = 0

    for dir_a in dir_as:
        try:
            move_one(dir_a, root_x, dry_run=dry_run)
            remove_a_directory(dir_a, dry_run=dry_run)
            success_count += 1
        except Exception as exc:
            failure_count += 1
            print(f"[失败] {dir_a}")
            print(f"  原因: {exc}")

    print("")
    print(f"完成。成功: {success_count}，失败: {failure_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Traverse O/A directories, extract the only *_content_list_v2.json from each A into X, then delete A."
    )
    parser.add_argument("root_o", help="总目录 O，下面包含很多 A 目录")
    parser.add_argument("root_x", help="目标目录 X，与 O 无关")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="实际执行移动和删除。默认仅 dry-run 预演。",
    )
    args = parser.parse_args()

    process_root(
        root_o=Path(args.root_o),
        root_x=Path(args.root_x),
        dry_run=not args.execute,
    )


if __name__ == "__main__":
    main()
