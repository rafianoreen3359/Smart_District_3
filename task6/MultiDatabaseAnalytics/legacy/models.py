from django.db import models


class Customer(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        managed = False
        db_table = 'customer'

    def __str__(self):
        return self.name
