from django.urls import path
from .views import (
    AdminClientListView,
    AdminRegenerateClientPasswordView,
    AdminShipmentListView,
    AdminUploadTxtView,
    ClientChangePasswordView,
    ClientShipmentSearchView,
)
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
    path('client/change-password/', ClientChangePasswordView.as_view(), name='client-change-password'),
    
    # Ruta protegida para administradores
    path('admin/upload-txt/', AdminUploadTxtView.as_view(), name='admin-upload-txt'),
    path('admin/clients/', AdminClientListView.as_view(), name='admin-client-list'),
    path('admin/shipments/', AdminShipmentListView.as_view(), name='admin-shipment-list'),
    path(
        'admin/clients/<int:client_id>/regenerate-password/',
        AdminRegenerateClientPasswordView.as_view(),
        name='admin-regenerate-client-password',
    ),
    
]