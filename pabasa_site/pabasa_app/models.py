from django.db import models

class User(models.Model):
    ROLE_CHOICES = [
        ("teacher", "Teacher"),
        ("student", "Student"),
    ]

    id = models.BigAutoField(primary_key=True)
    custom_id = models.CharField(max_length=20, unique=True, editable=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    sex = models.CharField(max_length=10)
    birth_month = models.PositiveSmallIntegerField()
    birth_day = models.PositiveSmallIntegerField()
    birth_year = models.PositiveSmallIntegerField()
    email = models.EmailField(unique=True)
    contact_no = models.CharField(max_length=20, blank=True, null=True)
    password_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)