# build_semantic_index.py (最终修正版 v2.0)

import sqlite3
import faiss
import numpy as np
# 导入正确的、最新的官方SDK客户端
from zai import ZhipuAiClient
import os
import time

# --- 配置 ---
DB_FILE_PATH = 'data/fault_knowledge.db'
TABLE_NAME = 'fault_records'
FAISS_INDEX_PATH = 'data/faiss_index.bin'
# 在这里填入你完整、正确的API Key
ZHIPU_API_KEY = "4934e4288eae4e148b3a2990c2686452.TcZ65AnmXH0e5n3P"

# --- 使用官方推荐方式初始化客户端 ---
try:
    if not ZHIPU_API_KEY or ZHIPU_API_KEY == "YOUR_ZHIPU_API_KEY":
        client = None
        print("错误：请先在脚本中设置你的 ZHIPU_API_KEY。")
    else:
        client = ZhipuAiClient(api_key=ZHIPU_API_KEY)
except Exception as e:
    client = None
    print(f"初始化ZhipuAiClient时出错: {e}")


def get_all_records_from_db():
    """从SQLite数据库获取所有记录。"""
    conn = sqlite3.connect(DB_FILE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(f"SELECT record_id, fault_phenomenon, resolution FROM {TABLE_NAME}")
    records = cursor.fetchall()
    conn.close()
    return [dict(record) for record in records]


def generate_embeddings(texts_to_embed, record_ids):
    """使用新的SDK为文本生成向量，并处理可能的API错误。"""
    embeddings_map = {}

    for i, text in enumerate(texts_to_embed):
        record_id = record_ids[i]
        try:
            response = client.embeddings.create(
                model="embedding-2",
                input=text,
            )
            # 将向量和ID关联起来
            embeddings_map[record_id] = response.data[0].embedding
            print(f"  - 成功生成向量 {i + 1}/{len(texts_to_embed)} (record_id: {record_id})")
            # 官方建议的API调用频率限制
            time.sleep(0.1)
        except Exception as e:
            print(f"  - 警告: 处理 record_id {record_id} 时出错: {e}。将跳过此条目。")
            continue

    return embeddings_map


def build_and_save_index():
    """构建并保存FAISS索引。"""
    if not client:
        print("客户端未成功初始化，脚本终止。")
        return

    print("开始构建语义索引...")

    # 1. 确保删除旧的、错误的索引文件
    if os.path.exists(FAISS_INDEX_PATH):
        os.remove(FAISS_INDEX_PATH)
        print(f"已删除旧的索引文件: {FAISS_INDEX_PATH}")

    # 2. 从数据库获取数据
    records = get_all_records_from_db()
    if not records:
        print("数据库中没有记录，无法创建索引。")
        return
    print(f"从数据库获取了 {len(records)} 条记录。")

    # 3. 准备数据
    texts_to_embed = [f"故障现象: {r['fault_phenomenon']}\n处理措施: {r['resolution']}" for r in records]
    record_ids = [r['record_id'] for r in records]

    # 4. 生成向量
    print("开始调用智谱API生成向量 (使用zai-sdk)...")
    embeddings_map = generate_embeddings(texts_to_embed, record_ids)

    if not embeddings_map:
        print("未能成功生成任何向量，索引创建失败。请检查API Key和网络连接。")
        return

    # 5. 准备用于FAISS的数据
    final_record_ids = np.array(list(embeddings_map.keys()))
    final_embeddings = np.array(list(embeddings_map.values())).astype('float32')

    # 6. 构建FAISS索引
    dimension = final_embeddings.shape[1]
    index = faiss.IndexIDMap(faiss.IndexFlatL2(dimension))
    index.add_with_ids(final_embeddings, final_record_ids)

    # 7. 保存索引到文件
    print(f"索引构建完成，总共成功索引了 {index.ntotal} 个向量。")
    faiss.write_index(index, FAISS_INDEX_PATH)
    print(f"语义索引已成功保存到: {FAISS_INDEX_PATH}")


if __name__ == "__main__":
    build_and_save_index()