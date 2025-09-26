# init_db.py

import pandas as pd
import sqlite3
import os

# --- 变量定义 (根据你的文件定制) ---
CSV_FILE_PATH = 'data/knowledge_base.csv'
DB_FILE_PATH = 'data/fault_knowledge.db'
TABLE_NAME = 'fault_records'


def create_database():
    """
    从 knowledge_base.csv 文件创建或重建SQLite数据库。
    """
    if os.path.exists(DB_FILE_PATH):
        print(f"数据库文件 '{DB_FILE_PATH}' 已存在，将删除重建。")
        os.remove(DB_FILE_PATH)

    try:
        print(f"正在从 '{CSV_FILE_PATH}' 读取数据...")
        # 使用 utf-8-sig 编码来处理可能存在的BOM头（常见于Windows导出的CSV）
        df = pd.read_csv(CSV_FILE_PATH, encoding='utf-8-sig')

        # 为了让列名在代码中更易用，我们将其转换为英文
        df.rename(columns={
            '序号': 'record_id',
            '故障单号': 'ticket_no',
            '专业': 'specialty',
            '设备名称': 'device_name',
            '站名': 'station_name',
            '接报时间': 'report_time',
            '修复时间': 'fix_time',
            '故障时间': 'fault_time',
            '故障现象': 'fault_phenomenon',
            '故障发生原因': 'fault_cause',
            '处理措施及结果': 'resolution',
            '消耗备件及数量': 'spare_parts',
            '处理人': 'handler',
            '备注': 'remarks'
        }, inplace=True)

    except FileNotFoundError:
        print(f"错误：源文件 '{CSV_FILE_PATH}' 未找到。请确保文件已放置在data文件夹下。")
        return
    except Exception as e:
        print(f"读取CSV文件时出错: {e}")
        return

    conn = sqlite3.connect(DB_FILE_PATH)
    print(f"正在将数据写入数据库表 '{TABLE_NAME}'...")
    df.to_sql(TABLE_NAME, conn, if_exists='replace', index=False)
    conn.close()

    print("数据库初始化成功！")
    print("数据库表结构和前2条数据预览（使用英文列名）:")

    # 验证数据库内容
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {TABLE_NAME} LIMIT 2")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        print(dict(row))


if __name__ == "__main__":
    create_database()