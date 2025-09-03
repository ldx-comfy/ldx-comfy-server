import fastapi
from . import forms, health
def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(forms.router)
    app.include_router(health.router)
    return app