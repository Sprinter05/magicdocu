from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
class AuthUser(AbstractUser):
    id = models.AutoField(primary_key=True)

    def __str__(self):
        if self.username != None:
            return self.username
        return "?"