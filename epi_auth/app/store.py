"""Cadastro de usuários (memória ou SQLite). Só guarda o hash da senha."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional

ROLES = ("OPERADOR", "SUPERVISOR")


@dataclass
class User:
    username: str
    name: str
    role: str
    password_hash: str
    active: bool = True

    def public(self) -> dict:
        return {"username": self.username, "name": self.name, "role": self.role, "active": self.active}


class UserStore:
    def __init__(self, path: str = "") -> None:
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path or ":memory:", check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, name TEXT NOT NULL, "
                         "role TEXT NOT NULL, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1)")
        self._db.commit()

    @staticmethod
    def _row(r) -> User:
        return User(username=r[0], name=r[1], role=r[2], password_hash=r[3], active=bool(r[4]))

    def get(self, username: str) -> Optional[User]:
        with self._lock:
            r = self._db.execute("SELECT username,name,role,password_hash,active FROM users WHERE username=?", (username,)).fetchone()
        return self._row(r) if r else None

    def list(self) -> list[User]:
        with self._lock:
            rows = self._db.execute("SELECT username,name,role,password_hash,active FROM users ORDER BY username").fetchall()
        return [self._row(r) for r in rows]

    def add(self, u: User) -> bool:
        with self._lock:
            try:
                self._db.execute("INSERT INTO users VALUES (?,?,?,?,?)", (u.username, u.name, u.role, u.password_hash, int(u.active)))
                self._db.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def update(self, u: User) -> None:
        with self._lock:
            self._db.execute("UPDATE users SET name=?, role=?, password_hash=?, active=? WHERE username=?",
                             (u.name, u.role, u.password_hash, int(u.active), u.username))
            self._db.commit()

    def count(self) -> int:
        with self._lock:
            return self._db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
