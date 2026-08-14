from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.models.mcp import MCPServer
from app.schemas.mcp import MCPCreate, MCPResponse, MCPUpdate
from app.services.mcp_service import create_mcp, get_mcps, update_mcp, delete_mcp

router = APIRouter()


@router.get("/mcps", response_model=list[MCPResponse])
async def list_mcps(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_mcps(db, user.id)


@router.get("/mcps/{mcp_id}", response_model=MCPResponse)
async def read_mcp(mcp_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MCPServer).where(MCPServer.id == mcp_id, MCPServer.owner_id == user.id))
    mcp = result.scalar_one_or_none()
    if not mcp:
        raise HTTPException(status_code=404, detail="MCPが見つかりません。")
    return mcp


@router.post("/mcps", response_model=MCPResponse)
async def create_mcp_endpoint(data: MCPCreate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await create_mcp(db, user.id, data)


@router.patch("/mcps/{mcp_id}", response_model=MCPResponse)
async def update_mcp_endpoint(mcp_id: str, data: MCPUpdate, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    mcp = await update_mcp(db, user.id, mcp_id, data)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCPが見つかりません。")
    return mcp


@router.delete("/mcps/{mcp_id}")
async def delete_mcp_endpoint(mcp_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    mcp = await delete_mcp(db, user.id, mcp_id)
    if not mcp:
        raise HTTPException(status_code=404, detail="MCPが見つかりません。")
    return {"id": mcp.id}
