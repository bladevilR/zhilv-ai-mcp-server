# app.py (最终智能版 v2.2 懒加载)

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import database
import semantic_service
from fastapi.concurrency import run_in_threadpool

# --- 懒加载机制 ---
# 全局标志，用于判断AI服务是否已经初始化
services_initialized = False


def ensure_ai_services_are_loaded():
    """
    这是一个依赖项函数。它会检查服务是否已加载，
    如果没加载，就执行一次耗时的初始化。
    """
    global services_initialized
    if not services_initialized:
        print("检测到首次AI请求，正在进行一次性加载AI服务...")
        semantic_service.initialize_ai_services()
        services_initialized = True
        print("AI服务加载完成，系统就绪！")


# --- 变量、安全配置 和 Pydantic模型 (不变) ---
API_KEY = "ZHILV_SUPER_SECRET_KEY_12345"
API_KEY_NAME = "X-API-KEY"
api_key_header_auth = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# 注意：我们移除了lifespan，因为我们不再在启动时加载
app = FastAPI(
    title="智履AI【智能版】MCP服务器",
    description="为智履AI提供具备语义搜索和动态知识库更新能力的API服务。",
    version="2.2.0",
)


async def get_api_key(api_key_header: str = Depends(api_key_header_auth)):
    if api_key_header != API_KEY:
        raise HTTPException(status_code=401, detail="无效的API密钥")


# ... (Pydantic模型定义与之前完全相同，此处省略以保持简洁)
class FaultRecordCreate(BaseModel):
    ticket_no: str;
    specialty: str;
    device_name: str;
    station_name: str;
    report_time: str;
    fix_time: str;
    fault_time: str;
    fault_phenomenon: str;
    fault_cause: str;
    resolution: str;
    spare_parts: str;
    handler: Optional[str] = None;
    remarks: Optional[str] = None


class FaultRecordUpdate(BaseModel):
    specialty: Optional[str] = None;
    device_name: Optional[str] = None;
    station_name: Optional[str] = None;
    report_time: Optional[str] = None;
    fix_time: Optional[str] = None;
    fault_time: Optional[str] = None;
    fault_phenomenon: Optional[str] = None;
    fault_cause: Optional[str] = None;
    resolution: Optional[str] = None;
    spare_parts: Optional[str] = None;
    handler: Optional[str] = None;
    remarks: Optional[str] = None


# --- API 端点定义 ---

@app.get("/", tags=["通用"])
def read_root():
    return {"status": "ok", "message": "欢迎使用智履AI【智能版】MCP服务器"}


# --- 【关键】在需要AI的接口上，添加 ensure_ai_services_are_loaded 依赖 ---
@app.get("/intelligent-search", tags=["智能问答"], summary="执行语义搜索并由GLM-4.5生成答案",
         dependencies=[Depends(ensure_ai_services_are_loaded)])
async def intelligent_search(query: str = Query(..., description="用户的自然语言问题"), deps=Depends(get_api_key)):
    try:
        similar_record_ids = await run_in_threadpool(semantic_service.semantic_search_in_faiss, query, top_k=3)
        if not similar_record_ids:
            raise HTTPException(status_code=404, detail="知识库中未找到相关记录。")

        context_records = await run_in_threadpool(database.get_records_by_ids, similar_record_ids)
        final_answer = await run_in_threadpool(semantic_service.ask_glm45_with_context, query, context_records)

        return {"answer": final_answer, "retrieved_context": context_records}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"处理智能问答时发生内部错误: {e}")


# 在所有需要操作索引的接口上，也添加这个依赖
@app.post("/records", status_code=status.HTTP_201_CREATED, tags=["数据库管理"], summary="新增记录 (同步更新语义索引)",
          dependencies=[Depends(ensure_ai_services_are_loaded)])
async def create_fault_record(record: FaultRecordCreate, deps=Depends(get_api_key)):
    record_dict = record.model_dump()
    result = await run_in_threadpool(database.add_fault_record, record_dict)
    new_record_id = result.get("record_id")

    if new_record_id:
        text_to_embed = f"故障现象: {record.fault_phenomenon}\n处理措施: {record.resolution}"
        await run_in_threadpool(semantic_service.add_to_index, new_record_id, text_to_embed)

    return result


# ... (为简洁，此处省略其他CRUD接口，但原理相同，即在接口定义中加入 dependencies=[Depends(ensure_ai_services_are_loaded)])
# 为了确保你复制的是最完整的代码，下面是全部接口的最终版本：

@app.put("/records/ticket/{ticket_no}", tags=["数据库管理"], summary="更新记录 (同步更新语义索引)",
         dependencies=[Depends(ensure_ai_services_are_loaded)])
async def update_fault_record(ticket_no: str, record_update: FaultRecordUpdate, deps=Depends(get_api_key)):
    old_record = await run_in_threadpool(database.get_record_by_ticket_no, ticket_no)
    if not old_record:
        raise HTTPException(status_code=404, detail=f"未找到故障单 {ticket_no}")

    record_id = old_record['record_id']
    update_data = record_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="请求体不能为空")

    result = await run_in_threadpool(database.update_fault_record, ticket_no, update_data)

    await run_in_threadpool(semantic_service.remove_from_index, record_id)
    updated_record = await run_in_threadpool(database.get_record_by_ticket_no, ticket_no)
    text_to_embed = f"故障现象: {updated_record['fault_phenomenon']}\n处理措施: {updated_record['resolution']}"
    await run_in_threadpool(semantic_service.add_to_index, record_id, text_to_embed)

    return result


@app.delete("/records/ticket/{ticket_no}", tags=["数据库管理"], summary="删除记录 (同步更新语义索引)",
            dependencies=[Depends(ensure_ai_services_are_loaded)])
async def delete_fault_record(ticket_no: str, deps=Depends(get_api_key)):
    record_to_delete = await run_in_threadpool(database.get_record_by_ticket_no, ticket_no)
    if not record_to_delete:
        raise HTTPException(status_code=404, detail=f"未找到故障单 {ticket_no}")

    record_id = record_to_delete['record_id']
    result = await run_in_threadpool(database.delete_fault_record, ticket_no)
    await run_in_threadpool(semantic_service.remove_from_index, record_id)

    return result


# 不需要AI服务的接口，就不用加依赖
@app.get("/records/ticket/{ticket_no}", tags=["数据库管理"], summary="按故障单号精确查询")
async def get_record_by_ticket(ticket_no: str, deps=Depends(get_api_key)):
    record = await run_in_threadpool(database.get_record_by_ticket_no, ticket_no)
    if not record:
        raise HTTPException(status_code=404, detail=f"未找到故障单号为 '{ticket_no}' 的记录。")
    return record


@app.get("/records/device/{device_name}", tags=["数据库管理"], summary="按设备名称模糊搜索")
async def search_records_by_device(device_name: str, deps=Depends(get_api_key)):
    records = await run_in_threadpool(database.search_records_by_device_name, device_name)
    if not records:
        raise HTTPException(status_code=404, detail=f"未找到与 '{device_name}' 相关的设备故障记录。")
    return records