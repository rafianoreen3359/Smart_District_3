from django.db import models


class PageView(models.Model):

    product_id = models.IntegerField()

    viewed_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"Product {self.product_id} View"


class EventLog(models.Model):

    event_name = models.CharField(max_length=100)

    details = models.TextField(blank=True)

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.event_name