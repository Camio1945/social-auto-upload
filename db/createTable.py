import sqlite3
from pathlib import Path

# 数据库文件路径（与脚本同目录，如果不存在会自动创建）
db_file = Path(__file__).parent / "database.db"

# 名称表：账号名称的唯一来源，user_info.userName 外键引用此表
CREATE_USER_NAME_SQL = '''
CREATE TABLE IF NOT EXISTS user_name (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    userName TEXT NOT NULL UNIQUE
)
'''

# 账号记录表（新建库时直接带外键）
CREATE_USER_INFO_SQL = '''
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0,
    FOREIGN KEY (userName) REFERENCES user_name (userName)
        ON UPDATE CASCADE ON DELETE RESTRICT
)
'''

# 旧库升级：SQLite 不支持 ALTER TABLE 加外键，需重建表
CREATE_USER_INFO_NEW_SQL = '''
CREATE TABLE user_info_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type INTEGER NOT NULL,
    filePath TEXT NOT NULL,
    userName TEXT NOT NULL,
    status INTEGER DEFAULT 0,
    FOREIGN KEY (userName) REFERENCES user_name (userName)
        ON UPDATE CASCADE ON DELETE RESTRICT
)
'''

# 同一名称在同一平台只能有一个账号
CREATE_USER_INFO_UNIQUE_INDEX_SQL = '''
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_info_user_name_type
    ON user_info (userName, type)
'''

# 文件记录表
CREATE_FILE_RECORDS_SQL = '''
CREATE TABLE IF NOT EXISTS file_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filesize REAL,
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT
)
'''


def table_exists(cursor, table_name):
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def backfill_user_names(cursor):
    """把已存在的账号名称回填到 user_name，避免升级后外键校验失败。"""
    cursor.execute("SELECT DISTINCT userName FROM user_info")
    for (user_name,) in cursor.fetchall():
        cursor.execute(
            "INSERT OR IGNORE INTO user_name (userName) VALUES (?)", (user_name,)
        )


def has_user_info_foreign_key(cursor):
    cursor.execute("PRAGMA foreign_key_list(user_info)")
    return any(row[2] == "user_name" for row in cursor.fetchall())


def rebuild_user_info(cursor):
    """重建 user_info 并保留原有数据，为其添加指向 user_name 的外键。"""
    cursor.execute("DROP TABLE IF EXISTS user_info_new")
    cursor.execute(CREATE_USER_INFO_NEW_SQL)
    cursor.execute('''
        INSERT INTO user_info_new (id, type, filePath, userName, status)
        SELECT id, type, filePath, userName, status FROM user_info
    ''')
    cursor.execute("DROP TABLE user_info")
    cursor.execute("ALTER TABLE user_info_new RENAME TO user_info")


def ensure_user_info(cursor):
    if not table_exists(cursor, "user_info"):
        cursor.execute(CREATE_USER_INFO_SQL)
        return
    # 已存在旧表：先回填名称，再按需补上外键
    backfill_user_names(cursor)
    if not has_user_info_foreign_key(cursor):
        rebuild_user_info(cursor)
        print("✅ user_info 已升级并添加 user_name 外键")


def ensure_user_info_unique_index(cursor):
    """为 (userName, type) 建唯一索引；历史重复数据会导致建索引失败。"""
    try:
        cursor.execute(CREATE_USER_INFO_UNIQUE_INDEX_SQL)
    except sqlite3.IntegrityError:
        print("⚠️ 存在同一名称同一平台的重复账号，未能创建唯一索引，请先清理重复数据")


def main():
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    cursor.execute(CREATE_USER_NAME_SQL)
    ensure_user_info(cursor)
    ensure_user_info_unique_index(cursor)
    cursor.execute(CREATE_FILE_RECORDS_SQL)

    conn.commit()
    conn.close()
    print("✅ 表创建成功")


if __name__ == "__main__":
    main()
