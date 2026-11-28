from .models import PageView, EventLog


class ProductViewMiddleware:

    def __init__(self, get_response):

        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        return response

    def process_view(
        self, request, view_func, view_args, view_kwargs
    ):

        # Check product detail page
        if request.resolver_match.url_name == 'product_detail':

            product_id = view_kwargs.get('product_id')

            if product_id:

                # Save view in analytics database
                PageView.objects.using('analytics').create(
                    product_id=product_id
                )

                # Save event
                EventLog.objects.using('analytics').create(
                    event_name='Product Viewed',
                    details=f'Product ID: {product_id}'
                )

        return None