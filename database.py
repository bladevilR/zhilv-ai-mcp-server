# database.py

import sqlite3
from typing import List, Dict, Any, Optional

# --- 变量定义 ---
DB_FILE_PATH = 'data/fault_knowledge.db'
TABLE_NAME = 'fault_records'


def get_db_connection():
    """建立并返回一个数据库连接"""
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# --- 查询 (Read) 函数 - 已有 ---
def get_record_by_ticket_no(ticket_no: str) -> Optional[Dict[str, Any]]:
    """根据故障单号，查询单条精确的故障记录。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} WHERE ticket_no = ?", (ticket_no,))
    record = cursor.fetchone()
    conn.close()
    return dict(record) if record else None


def search_records_by_device_name(device_name: str) -> List[Dict[str, Any]]:
    """根据设备名称，模糊搜索相关的故障记录列表。"""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = f"SELECT * FROM {TABLE_NAME} WHERE device_name LIKE ?"
    search_term = f"%{device_name}%"
    cursor.execute(query, (search_term,))
    records = cursor.fetchall()
    conn.close()
    return [dict(record) for record in records]


# --- 新增 (Create) 函数 ---
def add_fault_record(record_data: Dict[str, Any]) -> Dict[str, Any]:
    """新增一条故障记录到数据库。"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 动态构建插入语句
    columns = ', '.join(record_data.keys())
    placeholders = ', '.join(['?'] * len(record_data))
    values = tuple(record_data.values())

    query = f"INSERT INTO {TABLE_NAME} ({columns}) VALUES ({placeholders})"

    cursor.execute(query, values)
    conn.commit()

    # 获取刚刚插入的记录的 record_id (假设它是自增的)
    new_record_id = cursor.lastrowid
    conn.close()

    return {"status": "success", "record_id": new_record_id, "data": record_data}


# --- 修改 (Update) 函数 ---
def update_fault_record(ticket_no: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """根据故障单号，更新一条记录。"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 动态构建更新语句
    set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(ticket_no)

    query = f"UPDATE {TABLE_NAME} SET {set_clause} WHERE ticket_no = ?"

    cursor.execute(query, tuple(values))
    conn.commit()

    # 检查是否真的更新了数据
    updated_rows = cursor.rowcount
    conn.close()

    if updated_rows > 0:
        return {"status": "success", "message": f"故障单 {ticket_no} 已更新。"}
    else:
        return {"status": "not_found", "message": f"未找到故障单 {ticket_no}。"}


# --- 删除 (Delete) 函数 ---
def delete_fault_record(ticket_no: str) -> Dict[str, Any]:
    """根据故障单号，删除一条记录。"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = f"DELETE FROM {TABLE_NAME} WHERE ticket_no = ?"

    cursor.execute(query, (ticket_no,))
    conn.commit()

    deleted_rows = cursor.rowcount
    conn.close()

    if deleted_rows > 0:
        return {"status": "success", "message": f"故障单 {ticket_no} 已被删除。"}
    else:
        return {"status": "not_found", "message": f"未找到故障单 {ticket_no}。"}


# (在 database.py 文件末尾追加)

def get_records_by_ids(record_ids: List[int]) -> List[Dict[str, Any]]:
    """
    根据一个 record_id 列表，获取所有对应的记录。
    """
    if not record_ids:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()

    # 构建一个 (?, ?, ?) 格式的占位符字符串
    placeholders = ', '.join(['?'] * len(record_ids))
    query = f"SELECT * FROM {TABLE_NAME} WHERE record_id IN ({placeholders})"

    cursor.execute(query, record_ids)
    records = cursor.fetchall()
    conn.close()
    return [dict(record) for record in records]