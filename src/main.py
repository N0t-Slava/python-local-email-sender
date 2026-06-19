from fastapi import FastAPI
from src.database.sqlalchemy import init_db
from src.routers import router_send_email
from src.routers import router_campaigns_create
from src.routers import router_uploaded_image
from src.routers import router_get_current_user
from src.routers import router_add_single_contact
from src.routers import router_dashboard
from src.routers import router_suppression
from src.routers import router_sns_webhooks
from src.routers import router_unsubscribed
from src.routers import router_email_templates
from src.routers import router_domains
from src.routers import router_tracking

app = FastAPI()

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router_get_current_user.router)
app.include_router(router_campaigns_create.router)
app.include_router(router_uploaded_image.router)
app.include_router(router_send_email.router)
app.include_router(router_add_single_contact.router)
app.include_router(router_dashboard.router)
app.include_router(router_suppression.router)
app.include_router(router_sns_webhooks.router)
app.include_router(router_unsubscribed.router)
app.include_router(router_email_templates.router)
app.include_router(router_domains.router)
app.include_router(router_tracking.router)

@app.get("/")
async def root():
    return {"message": "Welcome to the API"}

@app.on_event("startup")
async def startup():
    await init_db()
