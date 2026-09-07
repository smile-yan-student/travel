"""一次性迁移脚本：SQLite（app/data/app.db）→ MySQL（travel_app）。

- 迁移 users：保留用户名与密码哈希（旧 sha256 格式），用户下次登录自动升级为 bcrypt。
- 迁移 trips：按用户名映射到新的 user_id。
- 幂等：已存在的同名用户跳过。
用法：
    cd backend && ./.venv/bin/python scripts/migrate_sqlite_to_mysql.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.userstore import _conn  # noqa: E402

SRC_DB = Path(__file__).resolve().parent.parent / "app" / "data" / "app.db"


def main() -> None:
    if not SRC_DB.exists():
        print("未发现 SQLite 数据文件，跳过迁移")
        return

    src = sqlite3.connect(str(SRC_DB))
    src.row_factory = sqlite3.Row
    users = src.execute(
        "SELECT id, username, password_hash, created_at FROM users"
    ).fetchall()
    trips = src.execute(
        "SELECT user_id, destination, days, style, lng, lat, distance_km, created_at FROM trips"
    ).fetchall()
    src.close()
    print(f"SQLite 读取：users={len(users)} trips={len(trips)}")

    mc = _conn()
    id_map: dict[int, int] = {}
    n_users = n_trips = 0
    with mc.cursor() as cur:
        for u in users:
            cur.execute("SELECT id FROM users WHERE username=%s", (u["username"],))
            exist = cur.fetchone()
            if exist:
                id_map[u["id"]] = exist["id"]
                continue
            cur.execute(
                "INSERT INTO users(username, password_hash, created_at) VALUES(%s,%s,%s)",
                (u["username"], u["password_hash"], u["created_at"]),
            )
            id_map[u["id"]] = cur.lastrowid
            n_users += 1

        for t in trips:
            new_uid = id_map.get(t["user_id"])
            if new_uid is None:
                continue
            cur.execute(
                "INSERT INTO trips(user_id, destination, days, style, lng, lat, distance_km, created_at) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (new_uid, t["destination"], t["days"], t["style"],
                 t["lng"], t["lat"], t["distance_km"], t["created_at"]),
            )
            n_trips += 1
    mc.close()
    print(f"迁移完成：users={n_users}（跳过已存在），trips={n_trips}")
    print("提示：旧账号密码为 sha256 格式，首次登录成功后会自动升级为 bcrypt")


if __name__ == "__main__":
    main()
