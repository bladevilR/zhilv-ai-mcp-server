# semantic_service.py

import faiss
import numpy as np
from zai import ZhipuAiClient
import os
from typing import List, Dict

# --- 配置 ---
FAISS_INDEX_PATH = 'data/faiss_index.bin'
ZHIPU_API_KEY = "4934e4288eae4e148b3a2990c2686452.TcZ65AnmXH0e5n3P"  # <-- 在这里再次填入你的智谱API Key

# --- 全局变量，确保服务启动时只加载一次模型和索引 ---
client = None
faiss_index = None


def initialize_ai_services():
    """
    初始化并加载所有AI相关的服务（模型客户端和FAISS索引）。
    这个函数应该在FastAPI应用启动时被调用。
    """
    global client, faiss_index
    print("正在初始化AI服务...")

    # 1. 初始化智谱AI客户端
    try:
        client = ZhipuAiClient(api_key=ZHIPU_API_KEY)
        print("智谱AI客户端初始化成功。")
    except Exception as e:
        print(f"初始化智谱AI客户端失败: {e}")
        # 在实际生产中，这里应该抛出异常，让应用启动失败
        return

    # 2. 加载FAISS索引文件
    if os.path.exists(FAISS_INDEX_PATH):
        try:
            faiss_index = faiss.read_index(FAISS_INDEX_PATH)
            print(f"FAISS索引加载成功，包含 {faiss_index.ntotal} 个向量。")
        except Exception as e:
            print(f"加载FAISS索引失败: {e}")
    else:
        print(f"警告：未找到FAISS索引文件 at {FAISS_INDEX_PATH}。智能搜索将不可用。")


def get_embedding_for_text(text: str) -> np.ndarray:
    """为单段文本生成向量。"""
    if not client:
        raise Exception("智谱AI客户端未初始化。")

    response = client.embeddings.create(
        model="embedding-2",
        input=text,
    )
    return np.array(response.data[0].embedding).astype('float32')


def semantic_search_in_faiss(query: str, top_k: int = 3) -> List[int]:
    """
    在FAISS中执行语义搜索。
    返回最相似的 top_k 个记录的 record_id 列表。
    """
    if not faiss_index or faiss_index.ntotal == 0:
        print("FAISS索引不可用或为空。")
        return []

    # 1. 为查询语句生成向量
    query_vector = get_embedding_for_text(query)
    query_vector = np.expand_dims(query_vector, axis=0)  # 转换为 (1, D) 的形状

    # 2. 在FAISS中搜索
    # D: 距离数组, I: 索引ID数组 (也就是我们的record_id)
    distances, indices = faiss_index.search(query_vector, top_k)

    # 返回 record_id 列表
    # -1 表示没有找到足够的邻居
    return [int(i) for i in indices[0] if i != -1]


def add_to_index(record_id: int, text_to_embed: str):
    """向FAISS索引中添加一个新的向量。"""
    if not faiss_index: return

    vector = get_embedding_for_text(text_to_embed)
    faiss_index.add_with_ids(np.expand_dims(vector, axis=0), np.array([record_id]))
    faiss.write_index(faiss_index, FAISS_INDEX_PATH)  # 持久化保存
    print(f"成功将 record_id {record_id} 添加到FAISS索引。")


def remove_from_index(record_id: int):
    """从FAISS索引中移除一个向量。"""
    if not faiss_index: return

    result = faiss_index.remove_ids(np.array([record_id]))
    # result > 0 表示成功移除了至少一个向量
    if result > 0:
        faiss.write_index(faiss_index, FAISS_INDEX_PATH)  # 持久化保存
        print(f"成功从FAISS索引中移除 record_id {record_id}。")


def ask_glm45_with_context(user_query: str, context_records: List[Dict]) -> str:
    """
    调用glm-4.5，结合上下文来回答用户问题。
    这正是 glm-4.5 发挥作用的地方！
    """
    if not client:
        raise Exception("智谱AI客户端未初始化。")

    # 1. 构建给大模型的提示词 (Prompt)
    context_str = "\n\n".join([
        f"故障案例 {i + 1} (故障单号: {r.get('ticket_no', 'N/A')}):\n"
        f"- 故障现象: {r.get('fault_phenomenon', 'N/A')}\n"
        f"- 故障原因: {r.get('fault_cause', 'N/A')}\n"
        f"- 处理措施: {r.get('resolution', 'N/A')}"
        for i, r in enumerate(context_records)
    ])

    prompt = (
        f"你是一名资深的设备维护专家，你的任务是基于下面提供的历史故障案例，用清晰、专业的语言回答用户的问题。\n\n"
        f"--- 历史故障案例参考 ---\n"
        f"{context_str}\n"
        f"--- 结束 ---\n\n"
        f"请严格根据以上案例，回答用户提出的问题：'{user_query}'"
    )

    # 2. 调用聊天模型
    response = client.chat.completions.create(
        model="glm-4.5",
        messages=[
            {"role": "system", "content": "你是一名资深的设备维护专家。"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,  # 增加一点创造性，但不过分
    )

    return response.choices[0].message.content