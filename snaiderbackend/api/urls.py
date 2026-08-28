from django.urls import path
from .views import ClientShipmentSearchView, AdminUploadTxtView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

urlpatterns = [
    path("auth/token/",TokenObtainPairView.as_view(),name="token-obtain-pair",),
    path("auth/token/refresh/",TokenRefreshView.as_view(),name="token-refresh",),
    path("auth/token/verify/",TokenVerifyView.as_view(),name="token-verify",),
   # Ruta pública para clientes
    path('shipments/search/', ClientShipmentSearchView.as_view(), name='client-shipment-search'),
    
    # Ruta protegida para administradores
    path('admin/upload-txt/', AdminUploadTxtView.as_view(), name='admin-upload-txt')
    
]