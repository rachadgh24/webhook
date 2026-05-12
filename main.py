from fastapi import FastAPI
from webhook import router as webhook_router
from UI import router as ui_router
app = FastAPI()

app.include_router(webhook_router)
app.include_router(ui_router)
