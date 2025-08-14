import fastapi
from . import run_wfs
def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(run_wfs.router)
    return app