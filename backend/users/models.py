from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('coach', 'Coach'),
        ('scout', 'Scout'),
        ('physio', 'Physio'),
        ('nutritionist', 'Nutritionist'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='coach')

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
