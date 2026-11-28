from django.shortcuts import render, get_object_or_404
from django.db.models import Count
from .models import Product
from analytics.models import PageView

def home(request):

    products = Product.objects.using('default').all()

    return render(
        request,
        'home.html',
        {'products': products}
    )

def product_detail(request, pk):

    product = get_object_or_404(
        Product.objects.using('default'),
        pk=pk
    )

    return render(
        request,
        'product_detail.html',
        {'product': product}
    )

def report(request):

    products = Product.objects.using('default').all()

    views = (
        PageView.objects.using('analytics')
        .values('product_id')
        .annotate(total_views=Count('id'))
    )

    view_counts = {
        item['product_id']: item['total_views']
        for item in views
    }

    report_data = []

    for product in products:

        report_data.append({
            'product': product,
            'total_views': view_counts.get(product.id, 0)
        })

    return render(
        request,
        'report.html',
        {'report_data': report_data}
    )