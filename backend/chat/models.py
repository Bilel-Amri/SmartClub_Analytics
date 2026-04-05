from django.db import models


class ChatMessage(models.Model):
    role = models.CharField(max_length=10)  # 'user' or 'assistant'
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f'[{self.role}] {self.content[:60]}'
