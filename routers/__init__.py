import fastapi
from . import forms, health, auth
def include_routers(app: fastapi.FastAPI) -> fastapi.FastAPI:
    app.include_router(forms.router)
    app.include_router(health.router)
    app.include_router(auth.router)
    return app