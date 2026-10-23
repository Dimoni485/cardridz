"""Служебные команды: сброс пароля пользователя.

Использование:
    python -m app.manage reset-password --username admin
"""

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import User


def reset_password(username: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if user is None:
            print(f"Пользователь '{username}' не найден", file=sys.stderr)
            return 1
        password = getpass.getpass("Новый пароль: ")
        if len(password) < 8:
            print("Пароль должен содержать не менее 8 символов", file=sys.stderr)
            return 1
        confirmation = getpass.getpass("Повторите пароль: ")
        if password != confirmation:
            print("Пароли не совпадают", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        db.commit()
        print(f"Пароль пользователя '{username}' изменён")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Управление Cardridz")
    subparsers = parser.add_subparsers(dest="command", required=True)
    reset_parser = subparsers.add_parser(
        "reset-password", help="Сбросить пароль пользователя"
    )
    reset_parser.add_argument("--username", default="admin")
    args = parser.parse_args()

    if args.command == "reset-password":
        return reset_password(args.username)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
