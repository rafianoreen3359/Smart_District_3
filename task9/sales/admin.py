from django.contrib import admin

from .models import Product, ProductImage, ReportRequest, Sale


@admin.register(ReportRequest)
class ReportRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "status", "email_status", "email_attempts", "created_at")
    list_filter = ("status", "email_status")


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "state", "processed_at")
    inlines = [ProductImageInline]


admin.site.register(Sale)
