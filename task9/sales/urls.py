from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("reports/", views.report_list, name="report_list"),
    path("reports/new/", views.report_create, name="report_create"),
    path("reports/<uuid:pk>/", views.report_status, name="report_status"),
    path("reports/<uuid:pk>/status.json", views.report_status_json, name="report_status_json"),
    path("reports/<uuid:pk>/download/", views.report_download, name="report_download"),
    path("products/", views.product_list, name="product_list"),
    path("products/new/", views.product_create, name="product_create"),
    path("products/<int:pk>/", views.product_detail, name="product_detail"),
    path("products/<int:pk>/status.json", views.product_status_json, name="product_status_json"),
]
