from aiogram import Router
from .registration import router as reg_router
from .family import router as family_router
from .gifts import router as gifts_router
from .admin import router as admin_router
from .common import router as common_router

def setup_routers() -> Router:
    main_router = Router()
    main_router.include_router(reg_router)
    main_router.include_router(family_router)
    main_router.include_router(gifts_router)
    main_router.include_router(admin_router)
    main_router.include_router(common_router)
    return main_router