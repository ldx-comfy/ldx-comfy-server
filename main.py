from fastapi import FastAPI
from routers import include_routers
from comfy.plugins import plugin_manager

# 创建FastAPI应用
app = include_routers(FastAPI())

# 初始化插件系统
@app.on_event("startup")
async def startup_event():
    """应用启动时初始化插件"""
    print("正在初始化插件系统...")
    plugin_manager.discover_and_register_plugins()

    # 初始化插件配置
    config = {
        'server_address': '106.52.220.169:6889',
        'output_dir': 'comfy_out_image'
    }
    plugin_manager.initialize_plugins(config)
    print("插件系统初始化完成")

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时清理插件"""
    print("正在清理插件系统...")
    plugin_manager.cleanup_plugins()
    print("插件系统清理完成")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000,reload=True,workers=1)
