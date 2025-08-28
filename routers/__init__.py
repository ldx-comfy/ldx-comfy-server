import fastapi
from . import wfs, forms
def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(wfs.router)
    app.include_router(forms.router)
    return app