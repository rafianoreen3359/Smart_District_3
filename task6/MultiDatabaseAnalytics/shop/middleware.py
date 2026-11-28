from analytics.models import PageView

class ProductViewMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        match = request.resolver_match

        if (
            match
            and match.url_name == 'product_detail'
            and response.status_code == 200
        ):

            product_id = match.kwargs.get('pk')

            PageView.objects.using('analytics').create(
                product_id=product_id
            )

        return response