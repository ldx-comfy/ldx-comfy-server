import fastapi
from . import wfs
def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(wfs.router)
    return app